from anthropic import Anthropic
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize the Anthropic client
client = Anthropic()


# System prompt defines your agent's identity and behaviour
SYSTEM_PROMPT = """You are an expert restaurant analytics assistant for 
Tunday Kababi, a popular Mughlai restaurant in Gurgaon, India. 

You have access to sales data for March and April 2026 including:
- Daily sales summaries
- Item-wise sales breakdown  
- Online orders from Swiggy and Zomato
- Menu item master data

Your job is to answer business questions clearly and concisely, 
always backing your answers with data. When you don't have data 
to answer something, say so clearly — never guess or hallucinate numbers.

Always be professional but conversational. Where relevant, 
highlight actionable business insights alongside the data."""


# Conversation history — starts empty
messages = []

print("🍢 Tunday Kababi Analytics Agent")
print("Type 'quit' to exit\n")

while True:
    # Get user input
    user_input = input("You: ").strip()
    
    if user_input.lower() == 'quit':
        print("Goodbye!")
        break
    
    if not user_input:
        continue
    
    # Add user message to history
    messages.append({
        "role": "user",
        "content": user_input
    })
    
    # Call Claude with full conversation history
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=messages        # <-- full history every time
    )
    
    assistant_message = response.content[0].text
    
    # Add Claude's response to history
    messages.append({
        "role": "assistant",
        "content": assistant_message
    })
    
    print(f"\nAgent: {assistant_message}\n")