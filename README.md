# Qwen2.5-VL Web Agent Mini Project

This project implements a web agent that uses the **Qwen2.5-VL-72B-Instruct** model to navigate webpages and complete tasks based on visual input. The agent observes webpage screenshots, predicts the next action (like clicking, typing, or scrolling), and executes it using Playwright.

-----

## Overview

The goal of this project is to create a web agent capable of performing real-world tasks on various websites. The agent operates in a loop: it captures a screenshot of the current webpage, sends it to the Qwen2.5-VL model to determine the next action, and then executes that action on the page. 

The core of the agent is `qwen_agent_final.py`, which manages the browser interaction, communication with the Qwen-VL model, and execution of actions.

-----

## Environment Setup

To run the agent, you'll need to set up a Conda environment with Python 3.11 and install the required packages.

1.  **Create and activate the Conda environment:** 

    ```bash
    conda create -n qwenvl_agent python=3.11
    conda activate qwenvl_agent
    ```

2.  **Install the necessary Python packages:** 

    ```bash
    pip install playwright
    pip install openai
    ```

3.  **Install Playwright's browser dependencies:** 

    ```bash
    playwright install
    ```

-----

##  How to Run

You can run the agent on a single, specific task or on a batch of validation tasks defined in a JSON file.

### Running a Single Task

The `run.sh` script is configured to execute the agent for a single, predefined task. You can modify this script to test different URLs and instructions.

**Example command from `run.sh`:**

```bash
python3 qwen_agent_final.py \
    --url https://www.vrbo.com \
    --task "On vrbo.com, find a vacation rental in Austin, TX" \
    --model "Qwen/Qwen2.5-VL-72B-Instruct-AWQ" \
    --endpoint "https://891c-141-212-113-40.ngrok-free.app/v1" \
    --max-steps 30 \
    --output "output.json"
```

### Running Multiple Validation Tasks

The `run_val_tasks.sh` script is designed to run the agent on a set of validation tasks. It reads task definitions from `val_tasks.json`, iterates through each one, and saves the output trajectory for each task in a separate indexed JSON file (e.g., `output_0.json`, `output_1.json`).

**To execute the validation tasks, simply run:**

```bash
bash run_val_tasks.sh
```

This script will sequentially execute each task defined in `val_tasks.json`, pausing for 30 seconds between tasks.

-----

## Project Files

  * `qwen_agent_final.py`: The main Python script that contains the web agent's logic.
  * `run.sh`: A shell script for running a single inference task.
  * `run_val_tasks.sh`: A shell script for running all validation tasks from `val_tasks.json`.
  * `val_tasks.json`: A JSON file containing the URLs and task descriptions for the validation set.