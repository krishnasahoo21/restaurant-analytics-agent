"""
app.py
------
Streamlit UI for the Tunday Kababi Analytics Agent.

Run with:
    streamlit run app.py
"""

import streamlit as st
from src.data_loader import load_all_data
from src.agent import RestaurantAgent

# ── Page Configuration ─────────────────────────────────────────────────────
# Must be the first Streamlit command
st.set_page_config(
    page_title = "Tunday Kababi Analytics",
    page_icon  = "🍢",
    layout     = "wide"
)

# ── Custom Styling ─────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Import fonts */
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=DM+Sans:wght@300;400;500&display=swap');

    /* Root variables */
    :root {
        --bg-primary:    #0D0D0D;
        --bg-secondary:  #161616;
        --bg-card:       #1E1E1E;
        --accent-gold:   #C9A84C;
        --accent-orange: #E8652A;
        --text-primary:  #F5F0E8;
        --text-muted:    #8A8478;
        --border:        #2A2A2A;
    }

    /* Global background */
    .stApp {
        background-color: var(--bg-primary);
        color: var(--text-primary);
        font-family: 'DM Sans', sans-serif;
    }

    /* Hide Streamlit default elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Main container */
    .main .block-container {
        padding: 2rem 3rem;
        max-width: 1000px;
        margin: 0 auto;
    }

    /* Header */
    .agent-header {
        text-align: center;
        padding: 2.5rem 0 1.5rem 0;
        border-bottom: 1px solid var(--border);
        margin-bottom: 2rem;
    }

    .agent-header h1 {
        font-family: 'Playfair Display', serif;
        font-size: 2.4rem;
        color: var(--accent-gold);
        margin: 0;
        letter-spacing: 0.02em;
    }

    .agent-header p {
        color: var(--text-muted);
        font-size: 0.9rem;
        margin: 0.5rem 0 0 0;
        font-weight: 300;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    /* Chat messages */
    .user-message {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 12px 12px 4px 12px;
        padding: 1rem 1.25rem;
        margin: 0.75rem 0 0.75rem 3rem;
        color: var(--text-primary);
        font-size: 0.95rem;
        line-height: 1.6;
    }

    .assistant-message {
        background: linear-gradient(135deg, #1A1410 0%, #1E1A14 100%);
        border: 1px solid #2D2515;
        border-left: 3px solid var(--accent-gold);
        border-radius: 4px 12px 12px 12px;
        padding: 1.25rem 1.5rem;
        margin: 0.75rem 3rem 0.75rem 0;
        color: var(--text-primary);
        font-size: 0.95rem;
        line-height: 1.7;
    }

    /* Message labels */
    .msg-label {
        font-size: 0.72rem;
        font-weight: 500;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        margin-bottom: 0.4rem;
    }

    .msg-label-user      {color: var(--text-muted);}
    .msg-label-assistant {color: var(--accent-gold);}

    /* Tool indicator */
    .tool-indicator {
        display: inline-block;
        background: #1A1A2E;
        border: 1px solid #2D2D4A;
        color: #7B8CDE;
        border-radius: 4px;
        padding: 0.2rem 0.6rem;
        font-size: 0.72rem;
        font-family: 'DM Mono', monospace;
        margin: 0.2rem 0.2rem 0.2rem 0;
        letter-spacing: 0.05em;
    }

    /* Suggested questions */
    .suggestions-label {
        color: var(--text-muted);
        font-size: 0.78rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.75rem;
    }

    /* Stats bar */
    .stats-bar {
        display: flex;
        gap: 1.5rem;
        padding: 1rem 1.5rem;
        background: var(--bg-secondary);
        border: 1px solid var(--border);
        border-radius: 8px;
        margin-bottom: 1.5rem;
    }

    .stat-item {
        text-align: center;
    }

    .stat-value {
        font-family: 'Playfair Display', serif;
        font-size: 1.1rem;
        color: var(--accent-gold);
        display: block;
    }

    .stat-label {
        font-size: 0.68rem;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }

    /* Input area */
    .stTextInput input {
        background: var(--bg-secondary) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        color: var(--text-primary) !important;
        font-family: 'DM Sans', sans-serif !important;
        font-size: 0.95rem !important;
        padding: 0.75rem 1rem !important;
    }

    .stTextInput input:focus {
        border-color: var(--accent-gold) !important;
        box-shadow: 0 0 0 2px rgba(201, 168, 76, 0.15) !important;
    }

    /* Buttons */
    .stButton button {
        background: var(--accent-gold) !important;
        color: #0D0D0D !important;
        border: none !important;
        border-radius: 8px !important;
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 500 !important;
        font-size: 0.9rem !important;
        padding: 0.6rem 1.5rem !important;
        letter-spacing: 0.03em !important;
        transition: all 0.2s ease !important;
    }

    .stButton button:hover {
        background: #D4B15E !important;
        transform: translateY(-1px) !important;
    }

    /* Divider */
    hr {
        border-color: var(--border) !important;
        margin: 1.5rem 0 !important;
    }

    /* Spinner */
    .stSpinner {color: var(--accent-gold) !important;}

    /* Scrollbar */
    ::-webkit-scrollbar {width: 4px;}
    ::-webkit-scrollbar-track {background: var(--bg-primary);}
    ::-webkit-scrollbar-thumb {
        background: var(--border);
        border-radius: 2px;
    }
</style>
""", unsafe_allow_html=True)


# ── Data Loading (cached) ──────────────────────────────────────────────────
# @st.cache_resource loads data ONCE and reuses it
# Without this, data reloads on every user interaction
# st.cache_resource is for objects that should be shared
# across all users and sessions (like a database connection)

@st.cache_resource
def get_agent():
    """
    Load data and initialise agent once.
    Cached so it doesn't reload on every interaction.
    """
    data  = load_all_data()
    agent = RestaurantAgent(data)
    return agent


# ── Session State ──────────────────────────────────────────────────────────
# st.session_state persists data across reruns
# Streamlit reruns the entire script on every interaction
# Without session_state, chat history would reset on every message

if "messages" not in st.session_state:
    st.session_state.messages = []          # chat display history

if "agent_ready" not in st.session_state:
    st.session_state.agent_ready = False

if "tools_called" not in st.session_state:
    st.session_state.tools_called = []      # track tools per message


# ── Header ─────────────────────────────────────────────────────────────────
st.markdown("""
<div class="agent-header">
    <h1>🍢 Tunday Kababi</h1>
    <p>Restaurant Analytics Agent · March – April 2026</p>
</div>
""", unsafe_allow_html=True)


# ── Stats Bar ──────────────────────────────────────────────────────────────
st.markdown("""
<div class="stats-bar">
    <div class="stat-item">
        <span class="stat-value">₹2,91,829</span>
        <span class="stat-label">April Net Sales</span>
    </div>
    <div class="stat-item">
        <span class="stat-value">489</span>
        <span class="stat-label">Total Orders</span>
    </div>
    <div class="stat-item">
        <span class="stat-value">↑12%</span>
        <span class="stat-label">MoM Growth</span>
    </div>
    <div class="stat-item">
        <span class="stat-value">331</span>
        <span class="stat-label">Online Orders</span>
    </div>
    <div class="stat-item">
        <span class="stat-value">277</span>
        <span class="stat-label">Unique Customers</span>
    </div>
    <div class="stat-item">
        <span class="stat-value">13</span>
        <span class="stat-label">Tools Available</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ── Initialise Agent ───────────────────────────────────────────────────────
agent = get_agent()


# ── Welcome Message ────────────────────────────────────────────────────────
if not st.session_state.messages:
    st.markdown("""
    <div class="assistant-message">
        <div class="msg-label msg-label-assistant">Analytics Agent</div>
        Welcome! I'm your restaurant analytics assistant for
        <strong>Tunday Kababi, HUDA Gurgaon</strong>.<br><br>
        I have access to your complete sales data for <strong>March and
        April 2026</strong> — including daily sales, item performance,
        Swiggy & Zomato orders, customer patterns and kitchen
        requirements.<br><br>
        Ask me anything about your business.
    </div>
    """, unsafe_allow_html=True)


# ── Chat History ───────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(f"""
        <div class="user-message">
            <div class="msg-label msg-label-user">You</div>
            {msg["content"]}
        </div>
        """, unsafe_allow_html=True)

    else:
        # Show tools that were called for this message
        tools_html = ""
        if msg.get("tools_called"):
            tools_html = "<div style='margin-bottom:0.75rem'>"
            for tool in msg["tools_called"]:
                tools_html += f'<span class="tool-indicator">⚙ {tool}</span>'
            tools_html += "</div>"

        st.markdown(f"""
        <div class="assistant-message">
            <div class="msg-label msg-label-assistant">Analytics Agent</div>
            {tools_html}
            {msg["content"]}
        </div>
        """, unsafe_allow_html=True)


# ── Suggested Questions ────────────────────────────────────────────────────
if not st.session_state.messages:
    st.markdown("""
    <div class="suggestions-label">Try asking</div>
    """, unsafe_allow_html=True)

    suggestions = [
        "What were the top selling items in April?",
        "How did Swiggy vs Zomato perform?",
        "Which day of the week is busiest?",
        "How much mutton keema should we procure?",
        "Who are our most loyal customers?",
        "How did April compare to March?"
    ]

    # Render suggestions as clickable buttons — 3 per row
    cols = st.columns(3)
    for i, suggestion in enumerate(suggestions):
        with cols[i % 3]:
            if st.button(suggestion, key=f"suggestion_{i}"):
                st.session_state.pending_question = suggestion
                st.rerun()


# ── Chat Input ─────────────────────────────────────────────────────────────
st.markdown("<div style='height: 1rem'></div>", unsafe_allow_html=True)
st.markdown("---")

col1, col2, col3 = st.columns([6, 1, 1])

with col1:
    user_input = st.text_input(
        label       = "question",
        placeholder = "Ask me anything about your restaurant's performance...",
        label_visibility = "collapsed",
        key         = "user_input"
    )

with col2:
    send_button = st.button("Send", use_container_width=True)

with col3:
    if st.button("Clear", use_container_width=True):
        st.session_state.messages = []
        agent.reset()
        st.rerun()


# ── Handle Input ───────────────────────────────────────────────────────────
# Check for pending question from suggestion buttons
question = None

if "pending_question" in st.session_state:
    question = st.session_state.pending_question
    del st.session_state.pending_question

elif send_button and user_input.strip():
    question = user_input.strip()

elif user_input.strip() and user_input != st.session_state.get("last_input"):
    # Handle Enter key
    question = user_input.strip()
    st.session_state.last_input = user_input


# ── Process Question ───────────────────────────────────────────────────────
if question:
    # Add user message to display history
    st.session_state.messages.append({
        "role":    "user",
        "content": question
    })

    # Show spinner while agent thinks
    with st.spinner("Analysing your data..."):

        # Track which tools get called
        tools_called = []

        # Monkey-patch execute_tool to track tool calls
        # This lets us show the user which tools were used
        import src.agent as agent_module
        original_execute = agent_module.execute_tool

        def tracking_execute(tool_name, tool_input):
            tools_called.append(tool_name)
            return original_execute(tool_name, tool_input)

        agent_module.execute_tool = tracking_execute

        # Get response from agent
        response = agent.chat(question)

        # Restore original execute_tool
        agent_module.execute_tool = original_execute

    # Add assistant response to display history
    st.session_state.messages.append({
        "role":         "assistant",
        "content":      response,
        "tools_called": tools_called
    })

    # Rerun to display new messages
    st.rerun()