# Use an intermediate image to install tc
FROM alpine:latest AS builder

# Install iproute2 package which includes tc
RUN apk update && apk add --no-cache iproute2

# Create a directory to hold the necessary files
RUN mkdir -p /tc-root/sbin /tc-root/lib /tc-root/lib64

# Copy the tc binary to the created directory
RUN cp /sbin/tc /tc-root/sbin/

# Find and copy necessary shared libraries
RUN ldd /sbin/tc | grep -o '/[^ ]*' | xargs -I '{}' cp -v '{}' /tc-root/lib/

# Copy necessary linker/loader files
RUN cp -v /lib/ld-musl-x86_64.so.1 /tc-root/lib/

# Copy the necessary files to the final image
FROM rancher/k3s:v1.30.2-k3s2
COPY --from=builder /tc-root /