# Use a base image like Python if you plan to write your script in Python
FROM python:3.8

# Install any necessary dependencies
# For example, you might need Docker SDK for Python
RUN pip install docker-compose

# Copy your script into the container
COPY main.py /main.py

# Set the entry point of the container to your script
ENTRYPOINT ["python", "/main.py"]
