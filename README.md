# MetaGPT Chainlit App with Web Search

This is a MetaGPT-powered Chainlit application that creates a complete software development team with web search capabilities.

## Features

- **Complete Development Team**: Product Manager, Architect, Project Manager, Engineers, QA Engineer, and Deployer
- **Web Search Integration**: All agents can search the web for latest information and best practices
- **Enhanced Logging**: All search activities are logged and visible in both console and Chainlit interface
- **Custom Deployer**: Creates executable files for different project types
- **Real-time Collaboration**: Team members work together to build your project
- **Modern UI**: Beautiful Chainlit interface with progress updates

## Search Activity Logging

The application provides comprehensive logging of all web search activities:

### Console Logs
- All search queries and results are logged to the console
- Search activities are also saved to `search_activities.log`
- Each agent's search activity is clearly identified

### Chainlit Interface
- Real-time updates when agents start searching
- Progress indicators for search completion
- Search results summary at the end of each project
- Clear visibility of what each agent is researching

### Example Log Output
```
🔍 [Product Manager] Searching web for: 'latest market trends and best practices for React e-commerce'
✅ [Product Manager] Search completed successfully
🎯 Product Manager is conducting market research...
✅ Product Manager market research completed
```

## Testing Search Functionality

Run the test script to verify your search setup:

```bash
python test_search.py
```

This will:
- Check if your SERPER_API_KEY is configured
- Test a sample search query
- Show you how to run the full application

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Variables

Create a `.env` file in the root directory with your API keys:

```env
# Required for MetaGPT
OPENAI_API_KEY=your_openai_api_key_here

# Required for web search functionality
SERPER_API_KEY=your_serper_api_key_here
```

### 3. Get API Keys

- **OpenAI API Key**: Get from [OpenAI Platform](https://platform.openai.com/api-keys)
- **Serper API Key**: Get from [Serper.dev](https://serper.dev/) for web search functionality

### 4. Run the Application

```bash
chainlit run app.py
```

The app will be available at `http://localhost:8000`

## How It Works

1. **User Input**: Describe your project idea
2. **Team Assembly**: MetaGPT creates a development team
3. **Web Research**: Each agent searches for relevant information
4. **Collaboration**: Team members work together to build your project
5. **Deployment**: Deployer creates executable files
6. **Delivery**: Complete project with running instructions

## Agent Capabilities

- **Product Manager**: Market research, user stories, competitive analysis
- **Architect**: Latest tech trends, architecture patterns, system design
- **Engineer**: Coding best practices, libraries, implementation
- **QA Engineer**: Testing tools, quality assurance methods
- **Deployer**: Deployment strategies, hosting options, executable creation

## Example Projects

- React applications with modern UI
- E-commerce platforms
- Data analytics dashboards
- Mobile-responsive websites
- API services and backends

## Troubleshooting

- **Web Search Not Working**: Ensure `SERPER_API_KEY` is set in your `.env` file
- **Project Generation Fails**: Check your `OPENAI_API_KEY` and internet connection
- **Server Issues**: Make sure port 8000 is available

## Contributing

Feel free to submit issues and enhancement requests!

## Project Structure

```
├── app.py              # Main Chainlit application with MetaGPT integration
├── chainlit.md         # Welcome page content
├── requirements.txt    # Python dependencies including MetaGPT
├── README.md          # This file
```

## Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- MetaGPT configuration (already set up)

## Installation and setup

1. Download this project
2. Navigate to the project directory
3. Install the required dependencies
4. Set MetaGPT configuration by initializing ``` metagpt --init-config ``` or by manually creating ```~/.metagpt/config2.yaml```
5. Configure the `~/.metagpt/config2.yaml` file according to your need.


## Running the Application

1. Start the Chainlit application:

```
chainlit run app.py
```

2. Open your web browser and go to `http://localhost:8000`

3. Start describing the website you want to create!

## How It Works

1. User Input: User describes the website they want.
2. MetaGPT Processing: The system combines the user's input with creating a basic html,css,javascript website.
3. App Generation: MetaGPT generates a complete website structure
4. Results Display: The chat interface shows the generated project structure and files






