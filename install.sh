#!/bin/bash

# Check if Go is installed
if ! type go >/dev/null 2>&1; then
  echo "Go is not installed. Please install Go and try again."
  exit 1
fi

# Set GOPATH if not set
if [ -z "$GOPATH" ]; then
  export GOPATH=$HOME/go
fi

# Create necessary directories if they don't exist
mkdir -p $GOPATH/src/comai
mkdir -p $GOPATH/bin

# Get the directory of the main.go file
go build -o comai main.go

# Move the comai binary to /usr/local/bin
sudo mv comai /usr/local/bin/

echo "comai has been installed successfully. Run 'comai' to use the tool."
