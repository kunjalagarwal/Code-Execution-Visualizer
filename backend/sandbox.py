import docker
import os
import tempfile
import json

client = docker.from_env()

# Ensure base image exists, we'll use a basic python image.
IMAGE_NAME = "python:3.10-slim"

def ensure_image():
    try:
        client.images.get(IMAGE_NAME)
    except docker.errors.ImageNotFound:
        client.images.pull(IMAGE_NAME)

def execute_code_in_sandbox(code: str, stdin: str):
    ensure_image()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Write user code
        code_path = os.path.join(temp_dir, "user_code.py")
        with open(code_path, "w", encoding="utf-8") as f:
            f.write(code)
            
        # Write stdin if any
        stdin_path = os.path.join(temp_dir, "stdin.txt")
        with open(stdin_path, "w", encoding="utf-8") as f:
            f.write(stdin)

        # We need to copy our tracer_script into the temp dir so it can be mounted.
        tracer_source = os.path.join(os.path.dirname(__file__), "tracer_script.py")
        tracer_dest = os.path.join(temp_dir, "tracer_script.py")
        with open(tracer_source, "r", encoding="utf-8") as fs, open(tracer_dest, "w", encoding="utf-8") as fd:
            fd.write(fs.read())

        try:
            # Run the container
            container = client.containers.run(
                image=IMAGE_NAME,
                command=["python", "/app/tracer_script.py", "/app/user_code.py", "/app/stdin.txt"],
                volumes={
                    temp_dir: {'bind': '/app', 'mode': 'ro'}
                },
                working_dir="/app",
                mem_limit="128m",   # Limit memory to 128MB
                network_disabled=True, # Prevent external requests
                user="1000:1000", # Run as non-root
                remove=True,
                detach=False,
                stdout=True,
                stderr=True,
                environment={"PYTHONUNBUFFERED": "1"},
                # Stop it if it exceeds timeout, achieved through a healthcheck or manual timeout. 
                # docker sdk .run waits, we could wait in a thread, but for simplicity we rely on 
                # the trace length limit acting fast. Let's add a timeout argument or simple handling.
            )
            # Find the generated output by printing it from docker
            result_str = container.decode('utf-8')
            # Extract JSON from STDOUT. Output might have some standard prints, 
            # tracer will print a specific delimiter if needed, or we just parse the last valid JSON.
            # Usually tracer dumps JSON at the end.
            lines = result_str.strip().split('\n')
            for line in lines[::-1]:
                if line.startswith('['):
                    try:
                        return {"success": True, "trace": json.loads(line)}
                    except json.JSONDecodeError:
                        pass
            
            # If no JSON found, maybe it errored out gracefully in tracer
            return {"success": False, "error": result_str}
            
        except docker.errors.ContainerError as e:
            # Code failed (Syntax error, exception, timeout etc)
            error_msg = e.stderr.decode('utf-8') if e.stderr else e.container.logs().decode('utf-8')
            return {"success": False, "error": error_msg}
