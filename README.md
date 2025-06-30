# MetaGPT

A chat application built with Chainlit and MetaGPT.

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

## Project Structure

```
├── app.py              # Main Chainlit application with MetaGPT integration
├── chainlit.md         # Welcome page content
├── requirements.txt    # Python dependencies including MetaGPT
├── README.md          # This file
```

## How It Works

1. User Input: User describes the website they want.
2. MetaGPT Processing: The system combines the user's input with creating a basic html,css,javascript website.
3. App Generation: MetaGPT generates a complete website structure
4. Results Display: The chat interface shows the generated project structure and files






