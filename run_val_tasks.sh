#!/bin/bash

# Path to the JSON file containing the tasks.
JSON_FILE="val_tasks.json"

# Common arguments for the Python script execution.
MODEL="Qwen/Qwen2.5-VL-72B-Instruct-AWQ"
ENDPOINT="https://891c-141-212-113-40.ngrok-free.app/v1"
MAX_STEPS=30

# Check if the JSON file exists.
if [ ! -f "$JSON_FILE" ]; then
    echo "Error: JSON file not found at '$JSON_FILE'"
    exit 1
fi

# --- [FIX] ---
# Initialize a counter for indexed output file naming.
INDEX=0

# Use 'jq' to iterate over each item in the JSON file.
# The '-c' option outputs each JSON object on a single line.
# '.[]' iterates through all elements of the top-level array.
jq -c '.[]' "$JSON_FILE" | while IFS= read -r line; do
    # Extract the 'url' and 'task' values from each line (JSON object).
    # The '-r' option removes the quotes from the output string.
    URL=$(echo "$line" | jq -r '.url')
    TASK=$(echo "$line" | jq -r '.task')

    # --- [FIX] ---
    # Set the output filename using the index counter.
    OUTPUT_FILE="./trajectories/output_${INDEX}.json"

    echo "🚀 Starting task #${INDEX}: ${TASK}"
    echo "   - URL: ${URL}"
    echo "   - Output File: ${OUTPUT_FILE}"

    # Execute the Python script with the extracted variables.
    # Quoting variables ensures that values with spaces or special characters are handled correctly.
    python3 qwen_agent_final.py \
        --url "$URL" \
        --task "$TASK" \
        --model "$MODEL" \
        --endpoint "$ENDPOINT" \
        --max-steps "$MAX_STEPS" \
        --output "$OUTPUT_FILE"

    echo "✅ Task finished. Results saved to ${OUTPUT_FILE}."
    echo "----------------------------------------------------"
    
    # --- [FIX] ---
    # Increment the counter for the next loop iteration.
    INDEX=$((INDEX + 1))
    
    sleep 30 # Brief pause before starting the next task.
done

echo "🎉 All tasks have been completed."