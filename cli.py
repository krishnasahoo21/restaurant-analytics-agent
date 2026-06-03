"""
cli.py
------
Terminal-based chat interface for the analytics agent.
Alternative to the Streamlit UI — runs directly in VS Code terminal.

Run with:
    python cli.py
"""

from src.data_loader import load_all_data
from src.agent import RestaurantAgent

def main():
    print("\n" + "═"*60)
    print("  🍢 Tunday Kababi Analytics Agent — Terminal Mode")
    print("═"*60)
    print("  Type 'quit' to exit | 'reset' to clear history")
    print("  Type 'verbose' to toggle tool call logging")
    print("═"*60 + "\n")

    # Load data and initialise agent
    print("Loading data...")
    data  = load_all_data()
    agent = RestaurantAgent(data)

    verbose = False

    print("\nAgent ready! Ask me anything.\n")

    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()

            # Handle commands
            if not user_input:
                continue

            if user_input.lower() == "quit":
                print("\nGoodbye!")
                break

            if user_input.lower() == "reset":
                agent.reset()
                print("Conversation cleared.\n")
                continue

            if user_input.lower() == "verbose":
                verbose = not verbose
                print(f"Verbose mode: {'ON' if verbose else 'OFF'}\n")
                continue

            # Get response
            print("\nAgent: ", end="", flush=True)
            response = agent.chat(user_input, verbose=verbose)
            print(response)
            print()

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break

if __name__ == "__main__":
    main()