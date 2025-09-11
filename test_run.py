from transformers import pipeline

# Initialize the pipeline for text generation
pipe = pipeline("text-generation", model="openai/gpt-oss-20b")

# Generate text based on a given prompt
result = pipe("Who are you?")

# Print the result
print(result)