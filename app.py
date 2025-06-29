import chainlit as cl
from typing import Dict, Any
import os
from dotenv import load_dotenv
from metagpt.software_company import generate_repo
from metagpt.utils.project_repo import ProjectRepo
import shutil
import json
from datetime import datetime

# Load environment variables
load_dotenv()

@cl.on_chat_start
async def start():
    """Initialize the chat session"""
    await cl.Message(
        content="Hello! I'm your AI assistant by MetaGPT for creating basic websites."
    ).send()

@cl.on_message
async def main(message: cl.Message):
    """Handle incoming messages"""
    
    # Get the user message
    user_message = message.content
    
    # Create a MetaGPT prompt by combining user input with website creation ( we assume to create only basic websites)
    metagpt_prompt = f"{user_message} create a html,css,javascript website on it"
    
    try:
        # Show a loading message
        await cl.Message(
            content=f"Generating a website based on: '{user_message}'... This may take a moment."
        ).send()
        
        # Generate the repository using MetaGPT
        repo: ProjectRepo = generate_repo(metagpt_prompt)
        
        # Get the repository structure
        repo_structure = str(repo)
        
        # Create the "Request" directory
        request_dir = "Request"
        if os.path.exists(request_dir):
            # If directory exists, create a timestamped version
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            request_dir = f"Request_{timestamp}"
        
        os.makedirs(request_dir, exist_ok=True)
        
        # Save all project files to the Request directory
        if hasattr(repo, 'files') and repo.files:
            files_saved = []
            for file_path, file_content in repo.files.items():
                # Create the full file path
                full_file_path = os.path.join(request_dir, file_path)
                
                # Create directories if they don't exist
                os.makedirs(os.path.dirname(full_file_path), exist_ok=True)
                
                # Write the file content
                with open(full_file_path, 'w', encoding='utf-8') as f:
                    f.write(file_content)
                
                files_saved.append(file_path)
            
            # Create a project info file
            project_info = {
                "request": user_message,
                "metagpt_prompt": metagpt_prompt,
                "generated_at": datetime.now().isoformat(),
                "total_files": len(files_saved),
                "files": files_saved,
                "repository_structure": repo_structure
            }
            
            with open(os.path.join(request_dir, "project_info.json"), 'w', encoding='utf-8') as f:
                json.dump(project_info, f, indent=2)
            
            # Send success message with file information
            success_message = f"""Website generated successfully!

Project saved to: `{request_dir}/`

Repository Structure:
```
{repo_structure}
```

Files created ({len(files_saved)} total):
"""
            for file_path in files_saved[:10]:  # Show first 10 files
                success_message += f"- {file_path}\n"
            
            if len(files_saved) > 10:
                success_message += f"- ... and {len(files_saved) - 10} more files\n"
            
            success_message += f"\nYour website has been created based on your request: '{user_message}'"
            
            await cl.Message(content=success_message).send()
            
        else:
            # Fallback if no files are available
            await cl.Message(
                content=f"Website generated successfully!\n\nRepository Structure:\n```\n{repo_structure}\n```\n\nYour website has been created based on your request: '{user_message}'"
            ).send()
            
    except Exception as e:
        # Handle any errors
        error_message = f"Sorry, I encountered an error while generating your website: {str(e)}"
        await cl.Message(content=error_message).send()

@cl.on_chat_end
async def end():
    """Handle chat session end"""
    await cl.Message(content="Thank you for using MetaGPT!").send() 