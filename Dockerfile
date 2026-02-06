FROM teddysun/v2ray:latest

# Install Python3 for the reporter script
RUN apk add --no-cache python3 ca-certificates

# Expose the correct container port (8080)
EXPOSE 8080

# Copy the VLESS config into the container
COPY config.json /etc/v2ray/config.json

CMD ["v2ray", "run", "-config", "/etc/v2ray/config.json"]

# Copy the reporter script
COPY reporter.py /reporter.py

# Run the reporter script
CMD ["python3", "-u", "/reporter.py"]


# join telegram https://t.me/ragnarservers  for new updates 
# my telegram username is @Not_Ragnar
