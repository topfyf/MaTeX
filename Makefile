# This is the Makefile

# Build
build: main.py
	pyinstaller -F -n matex main.py
	chmod 755 dist/matex

# Clean
clean:
	-rm -rf build
	-rm -rf dist
	-rm -rf __pycache__
	-rm -rf matex.spec

# Install
install:
	cp dist/matex /usr/local/bin

# Uninstall
uninstall:
	-rm /usr/local/bin/matex
