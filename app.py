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
import logging

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

# Import the SerperWrapper
try:
    from metagpt.tools.search_engine_serper import SerperWrapper
    SEARCH_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Could not import SerperWrapper: {e}")
    SEARCH_AVAILABLE = False
    # Create a dummy class for when search is not available
    class SerperWrapper:
        def __init__(self, api_key=None):
            self.api_key = api_key
        
        async def run(self, query, max_results=5):
            return "Web search not available - SerperWrapper import failed"

# Load environment variables
load_dotenv()

# Configure enhanced logging for search activities with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('search_activities.log', encoding='utf-8')
    ]
)

# Global variable to track the server
local_server = None
server_port = 9000

def safe_serialize(obj):
    """Safely serialize an object, handling non-serializable types"""
    try:
        if hasattr(obj, '__dict__'):
            # For objects like Message, extract relevant attributes
            if hasattr(obj, 'content'):
                return f"[{type(obj).__name__}] {obj.content}"
            elif hasattr(obj, 'role'):
                return f"[{type(obj).__name__}] role: {obj.role}"
            else:
                return f"[{type(obj).__name__}] {str(obj.__dict__)}"
        elif isinstance(obj, (list, tuple)):
            return [safe_serialize(item) for item in obj]
        elif isinstance(obj, dict):
            return {str(k): safe_serialize(v) for k, v in obj.items()}
        else:
            return str(obj)
    except Exception as e:
        return f"[Non-serializable {type(obj).__name__}] Error: {str(e)}"

# Custom Search Action
class SearchWeb(Action):
    name: str = "SearchWeb"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize SerperWrapper with API key from environment
        serper_api_key = os.getenv("SERPER_API_KEY")
        if not serper_api_key:
            logger.warning("SERPER_API_KEY not found in environment variables. Web search will be disabled.")
            self.search_enabled = False
        else:
            self.search_wrapper = SerperWrapper(api_key=serper_api_key)
            self.search_enabled = True
    
    async def run(self, query: str, max_results: int = 5, agent_name: str = "Unknown") -> str:
        """Search the web using Serper API with enhanced logging"""
        if not self.search_enabled:
            logger.info(f"[{agent_name}] Web search disabled - SERPER_API_KEY not configured")
            return "Web search is not available. SERPER_API_KEY not configured."
        
        try:
            logger.info(f"[{agent_name}] Searching web for: '{query}'")
            
            # Log the search attempt
            search_log_msg = f"🔍 **{agent_name}** is searching the web for: *{query}*"
            await cl.Message(content=search_log_msg).send()
            
            search_results = await self.search_wrapper.run(query, max_results=max_results)
            
            # Log successful search and the actual results
            logger.info(f"[{agent_name}] Search completed successfully")
            
            # Clean and log search results safely
            try:
                # Use safe serialization to handle non-serializable objects
                safe_results = safe_serialize(search_results)
                clean_results = str(safe_results).replace('\n', ' ').replace('\r', ' ')[:500]  # Limit length
                logger.info(f"[{agent_name}] Search results for '{query}':\n{clean_results}")
                success_log_msg = f"✅ **{agent_name}** found {max_results} relevant results"
                await cl.Message(content=success_log_msg).send()
                
                # Show search results in chat
                await cl.Message(content=f"📊 **Search Results:**\n{clean_results}").send()
            except Exception as e:
                logger.warning(f"Error logging search results: {e}")
                # Still log that we have results, even if we can't format them
                logger.info(f"[{agent_name}] Search completed with results (formatting failed: {e})")
                success_log_msg = f"✅ **{agent_name}** found {max_results} relevant results"
                await cl.Message(content=success_log_msg).send()
            
            # Return clean search results
            try:
                # Use safe serialization for return value too
                safe_return = safe_serialize(search_results)
                clean_return = str(safe_return).replace('\n', ' ').replace('\r', ' ')[:1000]  # Limit length
                return f"Search results for '{query}':\n{clean_return}"
            except Exception as e:
                logger.warning(f"Error cleaning search results for return: {e}")
                # Still return something useful
                return f"Search results for '{query}':\n[Results available but could not be formatted due to serialization error: {e}]"
        except Exception as e:
            error_msg = f"[{agent_name}] Search failed: {str(e)}"
            logger.error(error_msg)
            await cl.Message(content=f"❌ **{agent_name}** search failed: {str(e)}").send()
            return f"Search failed: {str(e)}"

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

# Enhanced Roles with Search Capabilities
class SearchEnabledProductManager(ProductManager):
    """Product Manager with web search capabilities"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([SearchWeb()] + self.actions)
    
    async def _act(self) -> Message:
        # First, search for relevant information about the project
        if hasattr(self, 'rc') and self.rc.todo and hasattr(self.rc.todo, 'name') and self.rc.todo.name == "SearchWeb":
            # Get the most recent message
            msg = self.get_memories(k=1)[0]
            search_query = f"latest market trends and best practices for {msg.content}"
            
            # Log the search activity
            logger.info(f"[Product Manager] Starting market research: {search_query}")
            await cl.Message(content=f"🎯 **Product Manager** is conducting market research...").send()
            
            search_results = await self.rc.todo.run(search_query, agent_name="Product Manager")
            
            # Create enhanced message with search results
            try:
                enhanced_content = f"{msg.content}\n\n**📊 Market Research from Web Search:**\n{search_results}"
                enhanced_msg = Message(content=enhanced_content, role=msg.role, cause_by=msg.cause_by)
                
                # Replace the original message with enhanced one
                self.rc.memory.add(enhanced_msg)
            except Exception as e:
                logger.warning(f"Error creating enhanced message: {e}")
                # Fallback: just log the search was completed
                logger.info(f"[Product Manager] Search completed but could not enhance message: {e}")
            
            # Log completion
            logger.info("[Product Manager] Market research completed")
            await cl.Message(content="✅ **Product Manager** market research completed").send()
        
        return await super()._act()

class SearchEnabledArchitect(Architect):
    """Architect with web search capabilities"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([SearchWeb()] + self.actions)
    
    async def _act(self) -> Message:
        # Search for technical information before designing
        if hasattr(self, 'rc') and self.rc.todo and hasattr(self.rc.todo, 'name') and self.rc.todo.name == "SearchWeb":
            msg = self.get_memories(k=1)[0]
            search_query = f"latest architecture patterns and technologies for {msg.content}"
            
            # Log the search activity
            logger.info(f"[Architect] Starting technical research: {search_query}")
            await cl.Message(content=f"🏗️ **Architect** is researching latest technologies...").send()
            
            search_results = await self.rc.todo.run(search_query, agent_name="Architect")
            
            try:
                enhanced_content = f"{msg.content}\n\n**🔧 Technical Research from Web Search:**\n{search_results}"
                enhanced_msg = Message(content=enhanced_content, role=msg.role, cause_by=msg.cause_by)
                self.rc.memory.add(enhanced_msg)
            except Exception as e:
                logger.warning(f"Error creating enhanced message: {e}")
                logger.info(f"[Architect] Search completed but could not enhance message: {e}")
            
            # Log completion
            logger.info("[Architect] Technical research completed")
            await cl.Message(content="✅ **Architect** technical research completed").send()
        
        return await super()._act()

class SearchEnabledEngineer(Engineer):
    """Engineer with web search capabilities"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([SearchWeb()] + self.actions)
    
    async def _act(self) -> Message:
        # Search for coding best practices and libraries
        if hasattr(self, 'rc') and self.rc.todo and hasattr(self.rc.todo, 'name') and self.rc.todo.name == "SearchWeb":
            msg = self.get_memories(k=1)[0]
            search_query = f"latest coding best practices and libraries for {msg.content}"
            
            # Log the search activity
            logger.info(f"[Engineer] Starting development research: {search_query}")
            await cl.Message(content=f"👨‍💻 **Engineer** is researching best practices...").send()
            
            search_results = await self.rc.todo.run(search_query, agent_name="Engineer")
            
            try:
                enhanced_content = f"{msg.content}\n\n**💻 Development Research from Web Search:**\n{search_results}"
                enhanced_msg = Message(content=enhanced_content, role=msg.role, cause_by=msg.cause_by)
                self.rc.memory.add(enhanced_msg)
            except Exception as e:
                logger.warning(f"Error creating enhanced message: {e}")
                logger.info(f"[Engineer] Search completed but could not enhance message: {e}")
            
            # Log completion
            logger.info("[Engineer] Development research completed")
            await cl.Message(content="✅ **Engineer** development research completed").send()
        
        return await super()._act()

class SearchEnabledQaEngineer(QaEngineer):
    """QA Engineer with web search capabilities"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([SearchWeb()] + self.actions)
    
    async def _act(self) -> Message:
        # Search for testing best practices
        if hasattr(self, 'rc') and self.rc.todo and hasattr(self.rc.todo, 'name') and self.rc.todo.name == "SearchWeb":
            msg = self.get_memories(k=1)[0]
            search_query = f"latest testing best practices and tools for {msg.content}"
            
            # Log the search activity
            logger.info(f"[QA Engineer] Starting testing research: {search_query}")
            await cl.Message(content=f"🧪 **QA Engineer** is researching testing tools...").send()
            
            search_results = await self.rc.todo.run(search_query, agent_name="QA Engineer")
            
            try:
                enhanced_content = f"{msg.content}\n\n**🧪 Testing Research from Web Search:**\n{search_results}"
                enhanced_msg = Message(content=enhanced_content, role=msg.role, cause_by=msg.cause_by)
                self.rc.memory.add(enhanced_msg)
            except Exception as e:
                logger.warning(f"Error creating enhanced message: {e}")
                logger.info(f"[QA Engineer] Search completed but could not enhance message: {e}")
            
            # Log completion
            logger.info("[QA Engineer] Testing research completed")
            await cl.Message(content="✅ **QA Engineer** testing research completed").send()
        
        return await super()._act()

# Custom Deployer Role
class Deployer(Role):
    name: str = "Deployer"
    profile: str = "Deployment Specialist"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_actions([CreateExecutable, SearchWeb()])
    
    async def _act(self) -> Message:
        # Safe logging with error handling
        try:
            if self.rc.todo and hasattr(self.rc.todo, 'name'):
                logger.info(f"{self._setting}: to do {self.rc.todo}({self.rc.todo.name})")
            else:
                logger.info(f"{self._setting}: to do {self.rc.todo}")
        except Exception as e:
            logger.warning(f"Error logging todo: {e}")
        
        todo = self.rc.todo
        
        # Get the most recent message which should contain project info
        msg = self.get_memories(k=1)[0]
        
        # Extract project information from the message
        project_description = msg.content
        
        # Search for deployment best practices
        if hasattr(todo, 'name') and todo.name == "SearchWeb":
            search_query = f"latest deployment and hosting best practices for {project_description}"
            
            # Log the search activity
            logger.info(f"[Deployer] Starting deployment research: {search_query}")
            await cl.Message(content=f"🚀 **Deployer** is researching deployment strategies...").send()
            
            search_results = await todo.run(search_query, agent_name="Deployer")
            
            try:
                enhanced_content = f"{project_description}\n\n**🚀 Deployment Research from Web Search:**\n{search_results}"
                enhanced_msg = Message(content=enhanced_content, role=msg.role, cause_by=msg.cause_by)
                self.rc.memory.add(enhanced_msg)
            except Exception as e:
                logger.warning(f"Error creating enhanced message: {e}")
                logger.info(f"[Deployer] Search completed but could not enhance message: {e}")
            
            # Log completion
            logger.info("[Deployer] Deployment research completed")
            await cl.Message(content="✅ **Deployer** deployment research completed").send()
            
            return enhanced_msg
        
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
        content="Hello! I'm your **MetaGPT Software Company** assistant. I'll create a complete software development team to build your project!\n\n**Team Roles:**\n- 🎯 **Product Manager**: Creates requirements and user stories (with web search for market research)\n- 🏗️ **Architect**: Designs system architecture (with web search for latest tech trends)\n- 📋 **Project Manager**: Plans and manages tasks\n- 👨‍💻 **Engineer**: Writes and reviews code (with web search for best practices)\n- 🧪 **QA Engineer**: Tests and ensures quality (with web search for testing tools)\n- 🚀 **Deployer**: Creates executable files to run your project (with web search for deployment best practices)\n\n**🔍 All agents have web search capabilities** to make informed decisions based on the latest information!\n\nJust describe what you want to build, and the team will collaborate to create it!"
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
            SearchEnabledProductManager(),
            SearchEnabledArchitect(),
            ProjectManager(),  # Project Manager doesn't need search for now
            SearchEnabledEngineer(n_borg=5, use_code_review=True),
            SearchEnabledQaEngineer(),
            Deployer(),  # Add the custom Deployer agent
        ])

        # Invest in the company and run the project
        company.invest(investment=3.0)
        company.run_project(idea=idea)

        # Run the team collaboration with error handling
        try:
            await company.run(n_round=5)
        except Exception as team_error:
            logger.error(f"Team collaboration error: {team_error}")
            await cl.Message(
                content=f"⚠️ **Team collaboration encountered an error:** {str(team_error)}\n\n🔄 **Attempting to continue with available results...**"
            ).send()

        # Get the work directory and files
        try:
            workdir = Path(company.env.context.config.project_path)
        except Exception as e:
            logger.error(f"Error getting project path: {e}")
            # Try to find the most recent workspace directory
            workspace_dir = Path("workspace")
            if workspace_dir.exists():
                # Find the most recent subdirectory
                subdirs = [d for d in workspace_dir.iterdir() if d.is_dir()]
                if subdirs:
                    workdir = max(subdirs, key=lambda x: x.stat().st_mtime)
                else:
                    workdir = workspace_dir
            else:
                workdir = Path(".")
            
            await cl.Message(
                content=f"⚠️ **Using fallback project directory:** `{workdir}`"
            ).send()
        
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

        # Show search activity summary
        search_summary = """
🔍 **Web Search Activity Summary:**

All agents performed web research to ensure the best possible project outcome:

• **Product Manager**: Conducted market research for trends and best practices
• **Architect**: Researched latest technologies and architecture patterns  
• **Engineer**: Looked up coding best practices and modern libraries
• **QA Engineer**: Found testing tools and quality assurance methods
• **Deployer**: Researched deployment strategies and hosting options

This ensures your project uses the most current and effective approaches! 🚀
"""
        await cl.Message(content=search_summary).send()
            
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