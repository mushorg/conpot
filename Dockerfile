# Stage 1: Build stage
FROM python:3.8 AS conpot-builder

# Install required dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /opt/conpot

# Copy the source code to the container
COPY . .

# Install specific dependencies
RUN pip3 install --no-cache-dir .

# Stage 2: Runtime stage
FROM python:3.8-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN adduser --disabled-password --gecos "" conpot

# Create required directories and set permissions
RUN mkdir -p /var/log/conpot \
    && mkdir -p /usr/local/lib/python3.8/site-packages/conpot/tests/data/data_temp_fs/ftp \
    && mkdir -p /usr/local/lib/python3.8/site-packages/conpot/tests/data/data_temp_fs/tftp \
    && chown -R conpot:conpot /var/log/conpot \
    && chown -R conpot:conpot /usr/local/lib/python3.8/site-packages/conpot/tests/data

# Set working directory and copy dependencies from build stage
WORKDIR /home/conpot
COPY --from=conpot-builder /usr/local/lib/python3.8/ /usr/local/lib/python3.8/
COPY --from=conpot-builder /usr/local/bin/ /usr/local/bin/

# Set permissions for non-root user
RUN chown -R conpot:conpot /home/conpot

# Switch to non-root user
USER conpot
ENV PATH=$PATH:/home/conpot/.local/bin
ENV USER=conpot

# Set the default command
ENTRYPOINT ["conpot"]
CMD ["--template", "default", "--logfile", "/var/log/conpot/conpot.log", "-f", "--temp_dir", "/tmp"]