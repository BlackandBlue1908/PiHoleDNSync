# Use a slim version of the Python image for a smaller footprint
FROM python:3.8-slim

# Set a working directory in the container
WORKDIR /app

# Copy the requirements file first to leverage Docker cache
COPY requirements.txt /app/

# Install only the necessary Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy your script into the container
COPY main.py /app/

# Set the entry point of the container to your script
ENTRYPOINT ["python", "main.py"]

