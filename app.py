import chainlit as cl
from typing import Dict, Any
import os
from dotenv import load_dotenv
from pathlib import Path
import http.server
import socketserver
import threading
import time
import socket
import re
import webbrowser
import asyncio

# MetaGPT team-based imports
from init_setup import ChainlitEnv
from metagpt.roles import (
    Architect,
    Engineer,
    ProductManager,
    ProjectManager,
    QaEngineer,
)
from metagpt.team import Team
from metagpt.actions import Action
from metagpt.roles import Role
from metagpt.schema import Message
from metagpt.logs import logger

# Load environment variables
load_dotenv()

# Global variable to track the server
local_server = None
server_port = 9000

# Custom Deployer Action
class CreateExecutable(Action):
    name: str = "CreateExecutable"
    
    PROMPT_TEMPLATE: str = """
    Analyze the project structure and create appropriate executable files for the project.
    
    Project Description: {project_description}
    Project Files: {project_files}
    
    Based on the project type and files, create:
    1. For React/Node.js projects: package.json scripts and batch/shell files
    2. For Python projects: requirements.txt and run scripts
    3. For static HTML/CSS/JS: simple server scripts
    4. For other projects: appropriate executable files
    
    Return the executable files content in this format:
    
    ## File: filename.ext
    ```content
    file content here
    ```
    
    ## File: another_file.ext
    ```content
    another file content here
    ```
    
    Create practical, working executables that users can run immediately.
    """

    async def run(self, project_description: str, project_files: str, project_path: str):
        prompt = self.PROMPT_TEMPLATE.format(
            project_description=project_description,
            project_files=project_files
        )
        
        response = await self._aask(prompt)
        return self.parse_executables(response, project_path)
    
    def parse_executables(self, response: str, project_path: str) -> Dict[str, str]:
        """Parse the response and extract executable file contents"""
        executables = {}
        
        # Split by file sections
        file_sections = re.split(r'## File:\s*([^\n]+)', response)
        
        for i in range(1, len(file_sections), 2):
            if i + 1 < len(file_sections):
                filename = file_sections[i].strip()
                content = file_sections[i + 1].strip()
                
                # Extract content from code blocks
                code_match = re.search(r'```(?:[a-zA-Z]*)\n(.*?)```', content, re.DOTALL)
                if code_match:
                    executables[filename] = code_match.group(1).strip()
                else:
                    executables[filename] = content
        
        return executables

# Custom Deployer Role
class Deployer(Role):
    name: str = "Deployer"
    profile: str = "Deployment Specialist"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([CreateExecutable])
    
    async def _act(self) -> Message:
        logger.info(f"{self._setting}: to do {self.rc.todo}({self.rc.todo.name})")
        todo = self.rc.todo
        
        # Get the most recent message which should contain project info
        msg = self.get_memories(k=1)[0]
        
        # Extract project information from the message
        project_description = msg.content
        
        # Get project files from the workspace - handle case when env might not be available
        try:
            if hasattr(self, 'env') and self.env and hasattr(self.env, 'context'):
                project_path = self.env.context.config.project_path
            else:
                # Fallback: try to get project path from the team's workspace
                project_path = None
                if hasattr(self, '_context') and self._context:
                    project_path = getattr(self._context, 'project_path', None)
                
                if not project_path:
                    # Use a default path or skip execution
                    return Message(content="Project path not available yet. Will create executables after project is complete.", role=self.profile, cause_by=type(todo))
            
            project_files = self._get_project_files(project_path)
            
            # Create executables
            executables = await todo.run(project_description, project_files, project_path)
            
            # Write executable files to the project directory
            self._write_executables(executables, project_path)
            
            result_msg = f"Created {len(executables)} executable files:\n" + "\n".join([f"- {filename}" for filename in executables.keys()])
            
        except Exception as e:
            logger.error(f"Error in Deployer._act: {e}")
            result_msg = f"Deployer encountered an error: {str(e)}. Will retry after project completion."
        
        return Message(content=result_msg, role=self.profile, cause_by=type(todo))
    
    def _get_project_files(self, project_path: str) -> str:
        """Get a list of project files for analysis"""
        try:
            project_dir = Path(project_path)
            if not project_dir.exists():
                return "Project directory not found"
            
            files = []
            for file_path in project_dir.rglob("*"):
                if file_path.is_file() and not any(part.startswith('.') for part in file_path.parts):
                    relative_path = file_path.relative_to(project_dir)
                    files.append(str(relative_path))
            
            return "\n".join(sorted(files))
        except Exception as e:
            return f"Error reading project files: {str(e)}"
    
    def _write_executables(self, executables: Dict[str, str], project_path: str):
        """Write executable files to the project directory"""
        try:
            project_dir = Path(project_path)
            
            for filename, content in executables.items():
                file_path = project_dir / filename
                
                # Create parent directories if needed
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Write the file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                # Make executable on Unix-like systems
                if os.name != 'nt':  # Not Windows
                    try:
                        os.chmod(file_path, 0o755)
                    except:
                        pass
                        
        except Exception as e:
            logger.error(f"Error writing executables: {e}")

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
        # Reusing the address is allowed to avoid port conflicts
        socketserver.TCPServer.allow_reuse_address = True
        # Create server
        httpd = socketserver.TCPServer(("", port), Handler)
        local_server = httpd
        server_port = port
        # Start server in a separate thread
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()
        time.sleep(1)  
        return True, f"Server started on port {port}"
    except Exception as e:
        return False, f"Failed to start server: {e}"

def stop_local_server():
    """Stop the local HTTP server"""
    global local_server
    if local_server:
        local_server.shutdown()
        local_server.server_close()
        local_server = None

# https://docs.chainlit.io/concepts/starters
@cl.set_chat_profiles
async def chat_profile() -> list[cl.ChatProfile]:
    """Generates a chat profile containing starter messages which can be triggered to run MetaGPT

    Returns:
        list[chainlit.ChatProfile]: List of Chat Profile
    """
    return [
        cl.ChatProfile(
            name="MetaGPT Team",
            icon="/public/MetaGPT-new-log.jpg",
            markdown_description="A **MetaGPT software company** that takes a one line requirement as input and outputs **user stories / competitive analysis / requirements / data structures / APIs / documents, working websites**, etc., with full team collaboration.\n\n**Example projects you can request:**\n• Create a 2048 game with a modern web interface\n• Build a web-based Blackjack game with nice UI\n• Build a modern React todo application with drag-and-drop functionality\n• Create a React e-commerce store with product catalog and shopping cart\n• Build a React analytics dashboard with charts and data visualization\n• Create a professional company website for a tech startup",
        )
    ]

@cl.on_chat_start
async def start():
    """Initialize the chat session"""
    await cl.Message(
        content="Hello! I'm your **MetaGPT Software Company** assistant. I'll create a complete software development team to build your project!\n\n**Team Roles:**\n- 🎯 **Product Manager**: Creates requirements and user stories\n- 🏗️ **Architect**: Designs system architecture\n- 📋 **Project Manager**: Plans and manages tasks\n- 👨‍💻 **Engineer**: Writes and reviews code (with 5 team members)\n- 🧪 **QA Engineer**: Tests and ensures quality\n- 🚀 **Deployer**: Creates executable files to run your project\n\nJust describe what you want to build, and the team will collaborate to create it!"
    ).send()

@cl.on_message
async def main(message: cl.Message):
    """Handle incoming messages and run MetaGPT team"""
    
    # Stop any existing server before starting a new one
    stop_local_server()
    
    # Get the user message
    idea = message.content
    
    try:
        # Show a loading message
        await cl.Message(
            content=f"🚀 **Starting MetaGPT Software Company for:** '{idea}'\n\n⏳ **Team is assembling and starting work...** This may take several minutes as the team collaborates."
        ).send()
        
        # Create MetaGPT team with ChainlitEnv
        company = Team(env=ChainlitEnv())

        # Hire the software development team including the Deployer
        company.hire([
            ProductManager(),
            Architect(),
            ProjectManager(),
            Engineer(n_borg=5, use_code_review=True),
            QaEngineer(),
            Deployer(),  # Add the custom Deployer agent
        ])

        # Invest in the company and run the project
        company.invest(investment=3.0)
        company.run_project(idea=idea)

        # Run the team collaboration
        await company.run(n_round=5)

        # Get the work directory and files
        workdir = Path(company.env.context.config.project_path)
        
        await cl.Message(
            content=f"✅ **Team collaboration completed!**\n\n📁 **Project directory:** `{workdir}`"
        ).send()

        # Post-processing: Create executables if Deployer didn't run properly
        try:
            await cl.Message(content="🚀 **Creating executable files...**").send()
            
            # Create a temporary Deployer instance for post-processing
            deployer = Deployer()
            deployer.env = company.env  # Set the environment
            
            # Get project files
            project_files = deployer._get_project_files(str(workdir))
            
            # Create executables using the action directly
            create_executable_action = CreateExecutable()
            executables = await create_executable_action.run(
                project_description=idea,
                project_files=project_files,
                project_path=str(workdir)
            )
            
            # Write executable files
            deployer._write_executables(executables, str(workdir))
            
            if executables:
                await cl.Message(
                    content=f"✅ **Created {len(executables)} executable files for your project!**"
                ).send()
            
        except Exception as e:
            await cl.Message(
                content=f"⚠️ **Note:** Could not create executable files: {str(e)}"
            ).send()

        # Find all generated files
        files = []
        if workdir.exists():
            for file_path in workdir.rglob("*"):
                if file_path.is_file() and not any(part.startswith('.git') for part in file_path.parts):
                    files.append(file_path)
        
        if files:
            files_list = "\n".join([f"📄 {file.relative_to(workdir)}" for file in files])
            await cl.Message(
                content=f"**Generated Files:**\n```\n{files_list}\n```"
            ).send()
        
        # Look for executable files created by the Deployer
        executable_files = [f for f in files if f.suffix.lower() in ['.bat', '.sh', '.ps1', '.cmd'] or f.name in ['run.bat', 'run.sh', 'start.bat', 'start.sh', 'package.json', 'requirements.txt']]
        
        if executable_files:
            executable_list = "\n".join([f"🚀 {file.relative_to(workdir)}" for file in executable_files])
            
            # Provide specific instructions based on file types
            instructions = []
            for file in executable_files:
                if file.suffix.lower() == '.bat':
                    instructions.append(f"• Double-click `{file.name}` to run on Windows")
                elif file.suffix.lower() == '.sh':
                    instructions.append(f"• Run `./{file.name}` in terminal on Mac/Linux")
                elif file.name == 'package.json':
                    instructions.append(f"• Run `npm install && npm start` in the project directory")
                elif file.name == 'requirements.txt':
                    instructions.append(f"• Run `pip install -r requirements.txt` then `python main.py`")
            
            instruction_text = "\n".join(instructions) if instructions else "• Use the appropriate executable file for your operating system"
            
            await cl.Message(
                content=f"**🚀 Executable Files Created:**\n```\n{executable_list}\n```\n\n**💡 How to run your project:**\n{instruction_text}"
            ).send()
        
        # Look for HTML files to serve
        html_files = [f for f in files if f.suffix.lower() == '.html']
        serve_dir = None
        html_file_path = None
        
        # Try to find index.html or main.html
        for html_file in html_files:
            if html_file.name.lower() in ['index.html', 'main.html']:
                html_file_path = html_file
                serve_dir = html_file.parent
                break
        
        # If no index.html found, use the first HTML file
        if not html_file_path and html_files:
            html_file_path = html_files[0]
            serve_dir = html_file_path.parent
        
        if html_file_path and serve_dir:
            await cl.Message(
                content=f"🌐 **Found web application:** `{html_file_path.name}`"
            ).send()
            
            # Patch HTML to use module type for JavaScript
            if html_file_path.exists():
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
                        content="🔧 **Patched HTML** to properly load JavaScript modules."
                    ).send()

            # Start local server and open in browser
            try:
                await cl.Message(
                    content="🖥️ **Starting local web server...**"
                ).send()
                
                server_started, server_message = await asyncio.to_thread(start_local_server, str(serve_dir))
                
                if server_started:
                    html_filename = html_file_path.name
                    http_url = f"http://localhost:{server_port}/{html_filename}"
                    
                    await cl.Message(
                        content=f"✅ {server_message}\n\n🌐 **Website URL:** `{http_url}`"
                    ).send()
                    
                    # Open in default browser
                    await asyncio.to_thread(webbrowser.open, http_url)
                    
                    await cl.Message(
                        content="🚀 **Browser opened!** Your website is now running with full functionality."
                    ).send()
                    
                else:
                    await cl.Message(
                        content=f"⚠️ {server_message}\n\nFiles are available at: `{html_file_path}`"
                    ).send()
                
            except Exception as browser_error:
                await cl.Message(
                    content=f"⚠️ **Browser error:** {str(browser_error)}\n\nFiles are available at: `{html_file_path}`"
                ).send()
        
        else:
            await cl.Message(
                content="📁 **Project completed!** No web interface found, but all generated files are available in the project directory."
            ).send()

        # Show total cost
        total_cost = getattr(company.cost_manager, 'total_cost', 'N/A')
        await cl.Message(
            content=f"💰 **Total development cost:** `${total_cost}`"
        ).send()
            
    except Exception as e:
        # Handle any errors
        error_message = f"❌ **Error during team collaboration:** {str(e)}"
        await cl.Message(content=error_message).send()
        
        # Show debug information
        import traceback
        await cl.Message(
            content=f"**Debug Details:**\n```\n{traceback.format_exc()}\n```"
        ).send()

@cl.on_chat_end
async def end():
    """Handle chat session end"""
    # Stop the local server if running
    stop_local_server()
    await cl.Message(content="👋 **Thank you for using MetaGPT Software Company!** Team disbanded successfully.").send()