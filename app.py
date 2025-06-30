import chainlit as cl
from typing import Dict, Any
import os
from dotenv import load_dotenv
from metagpt.software_company import generate_repo
from metagpt.utils.project_repo import ProjectRepo
from metagpt.tools.web_browser_engine import WebBrowserEngine
from metagpt.configs.browser_config import BrowserConfig
import webbrowser
from pathlib import Path
import http.server
import socketserver
import threading
import time
import socket
import re

# Load environment variables
load_dotenv()

# Global variable to track the server
local_server = None
server_port = 9000

def start_local_server(directory, port=9000):
    """Start a local HTTP server to serve files from the given directory"""
    global local_server, server_port
    
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)
        
        def end_headers(self):
            # Add CORS headers to allow local development
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-control-allow-headers', 'Content-Type')
            # Add cache-control headers to prevent caching
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            super().end_headers()
    
    try:
        # Allow reusing the address to avoid port conflicts on restart
        socketserver.TCPServer.allow_reuse_address = True
        # Create server
        httpd = socketserver.TCPServer(("", port), Handler)
        local_server = httpd
        server_port = port
        # Start server in a separate thread
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()
        time.sleep(1)  # Give server time to start
        return True, f"Server started on port {port}"
    except Exception as e:
        return False, f"Failed to start server: {e}"

def stop_local_server():
    """Stop the local HTTP server"""
    global local_server
    if local_server:
        local_server.shutdown()
        local_server.server_close()  # Properly close the server
        local_server = None

@cl.on_chat_start
async def start():
    """Initialize the chat session"""
    await cl.Message(
        content="Hello! I'm your AI assistant by MetaGPT for creating basic websites."
    ).send()

@cl.on_message
async def main(message: cl.Message):
    """Handle incoming messages"""
    
    # Stop any existing server before starting a new one
    stop_local_server()
    
    # Get the user message
    user_message = message.content
    
    # Create a MetaGPT prompt by combining user input with website creation ( we assume to create only basic websites)
    metagpt_prompt = f"{user_message} create a complete functional website with HTML, CSS, and JavaScript. Make sure all files are properly linked and the website works without external dependencies."
    
    try:
        # Show a loading message
        await cl.Message(
            content=f"Generating a website based on: '{user_message}'... This may take a moment."
        ).send()
        
        # Generate the repository using MetaGPT
        repo: ProjectRepo = generate_repo(metagpt_prompt)
        
        await cl.Message(
            content=f"**Debug:** MetaGPT generation completed. Repository root: {repo.root_path}"
        ).send()
        
        # Get the repository structure
        repo_structure = str(repo)
        
        # The directory to serve files from
        serve_dir = None
        html_file_path = None
        
        # Determine the directory with the source files to serve
        project_name = Path(repo.root_path).name
        potential_serve_dir = Path(repo.root_path) / project_name
        
        if (potential_serve_dir / "index.html").exists():
            serve_dir = potential_serve_dir
            html_file_path = serve_dir / "index.html"
        elif (Path(repo.root_path) / "index.html").exists():
            serve_dir = Path(repo.root_path)
            html_file_path = serve_dir / "index.html"
        else:
            # Fallback to search for index.html
            for root, _, files in os.walk(repo.root_path):
                if "index.html" in files:
                    serve_dir = Path(root)
                    html_file_path = serve_dir / "index.html"
                    break

        if not serve_dir:
            await cl.Message(
                content="**Error:** Could not find `index.html` in the generated project. Cannot start web server."
            ).send()
            return
            
        await cl.Message(
            content=f"**Debug:** Serving files from: `{serve_dir}`"
        ).send()

        # After finding the directory, ensure index.html uses type="module" for app.js
        if html_file_path and html_file_path.exists():
            with open(html_file_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            
            # Replace any script tag referencing app.js with type="module"
            new_html_content = re.sub(
                r'<script\s+src=(["\'])app\.js\1.*?>',
                r'<script src="app.js" type="module">',
                html_content,
                flags=re.IGNORECASE
            )

            if new_html_content != html_content:
                with open(html_file_path, "w", encoding="utf-8") as f:
                    f.write(new_html_content)
                await cl.Message(
                    content="**Debug:** Patched `index.html` to include `type=\"module\"` for the script."
                ).send()

        # Send success message with file information
        success_message = f"""Website generated successfully!

Project is located at: `{repo.root_path}`

Repository Structure:
```
{repo_structure}
```
"""
        await cl.Message(content=success_message).send()
        
        # Enable browser view using MetaGPT's WebBrowserEngine
        if html_file_path:
            try:
                # Start a local HTTP server to serve the files
                await cl.Message(
                    content="Starting local HTTP server to serve website files..."
                ).send()
                
                # Start the local server
                server_started, server_message = start_local_server(str(serve_dir))
                
                if server_started:
                    # Use HTTP URL instead of file:// protocol
                    # Assuming the html file is named index.html
                    html_filename = html_file_path.name
                    http_url = f"http://localhost:{server_port}/{html_filename}"
                    
                    await cl.Message(
                        content=f"{server_message}\n\n"
                               f"Loading website via HTTP: `{http_url}`"
                    ).send()
                    
                    # Also open in default browser
                    webbrowser.open(http_url)
                    
                    await cl.Message(
                        content=" **Browser opened!** Your website is now displayed in your default browser with full CSS and JavaScript support."
                    ).send()
                    
                else:
                    # Fallback to file:// protocol if server fails
                    await cl.Message(
                        content=f"{server_message}\n\nUsing fallback method..."
                    ).send()
                    
                    file_url = html_file_path.as_uri()
                    webbrowser.open(file_url)
                    
                    await cl.Message(
                        content=f" **Fallback browser opened!**\n\n"
                               f"Note: CSS and JavaScript may not load properly due to browser security restrictions.\n"
                               f"File: `{html_file_path}`"
                    ).send()
                
            except Exception as browser_error:
                await cl.Message(
                    content=f"**Browser Engine Note:**\n\n"
                           f"Website generated successfully, but browser engine encountered an issue.\n\n"
                           f"File: `{html_file_path}`\n"
                           f"Error: {str(browser_error)}\n\n"
                           f"Trying to open in default browser..."
                ).send()
                
                # Fallback to default browser with HTTP server
                try:
                    server_started, server_message = start_local_server(str(serve_dir))
                    if server_started:
                        html_filename = html_file_path.name
                        http_url = f"http://localhost:{server_port}/{html_filename}"
                        webbrowser.open(http_url)
                        await cl.Message(
                            content=f"**Fallback browser opened!**\n\n"
                                   f"URL: `{http_url}`\n"
                                   f"Your website is now displayed in your default browser."
                        ).send()
                    else:
                        # Final fallback to file:// protocol
                        file_url = html_file_path.as_uri()
                        webbrowser.open(file_url)
                        await cl.Message(
                            content=f"**Final fallback browser opened!**\n\n"
                                   f"File: `{html_file_path}`\n"
                                   f"Note: CSS and JavaScript may not load properly."
                        ).send()
                except Exception as fallback_error:
                    await cl.Message(
                        content=f"**Browser Error:**\n\n"
                               f"Could not open browser automatically.\n\n"
                               f"Please manually open: `{html_file_path}`\n\n"
                               f"Error: {str(fallback_error)}"
                    ).send()
        else:
            await cl.Message(
                content="**Note:** No HTML file found to open in browser. Check the generated files in the workspace directory."
            ).send()

    except Exception as e:
        # Handle any errors
        error_message = f"Sorry, I encountered an error while generating your website: {str(e)}"
        await cl.Message(content=error_message).send()
        
        # Debug: Show full error details
        import traceback
        await cl.Message(
            content=f"🔍 **Debug Error Details:**\n```\n{traceback.format_exc()}\n```"
        ).send()

@cl.on_chat_end
async def end():
    """Handle chat session end"""
    # Stop the local server if it's running
    stop_local_server()
    await cl.Message(content="Thank you for using MetaGPT!").send() 