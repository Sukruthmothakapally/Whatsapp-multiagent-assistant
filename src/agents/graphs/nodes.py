import logging
import datetime
import json
import os
from typing import Dict, Any
import requests
from langchain_core.messages import HumanMessage, AIMessage

from agents.text_agents.groq import ask_groq, ask_routing_agent
from memory.short_term import get_memory, add_to_memory
from memory.long_term import query_qdrant, add_to_qdrant
from agents.audio_agents.speech_to_text import SpeechToText
from agents.audio_agents.text_to_speech import TextToSpeech
from agents.image_agents.image_to_text import ImageToText
from agents.image_agents.text_to_image import TextToImage

logger = logging.getLogger(__name__)

def is_error(response: str) -> bool:
    """Check if a response indicates an error."""
    return not response or response.lower().startswith("error:")

async def process_media_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Process different media types into text."""
    raw_input = state.get("raw_input")
    media_type = state.get("media_type")
    
    if media_type == "audio":
        logger.info("🎧 Detected audio input, invoking STT...")
        stt = SpeechToText()
        try:
            text = await stt.transcribe(raw_input)
            logger.info(f"✅ Transcribed to text: {text}")
            return {
                "messages": [HumanMessage(content=text)]
            }
        except Exception as e:
            logger.error(f"❗ STT error: {e}")
            error_msg = f"Sorry, I couldn't understand the audio: {e}"
            return {
                "messages": [HumanMessage(content="[Audio transcription failed]")],
                "response_text": error_msg,
                "routing_decision": "NONE"
            }

    elif media_type == "image":
        logger.info("🖼️ Detected image input, invoking ITT...")
        try:
            itt = ImageToText()
            text = await itt.analyze_image(raw_input)
            logger.info(f"✅ Image described as: {text}")
            return {
                "messages": [HumanMessage(content=text)]
            }
        except Exception as e:
            logger.error(f"❗ ITT error: {e}")
            error_msg = f"Sorry, I couldn't understand the image: {e}"
            return {
                "messages": [HumanMessage(content="[Image analysis failed]")],
                "response_text": error_msg,
                "routing_decision": "NONE"
            }
    
    # For text, just pass through
    return {
        "messages": [HumanMessage(content=raw_input)]
    }

async def routing_decision_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Determine routing strategy for the message."""
    # Get the most recent message
    message = state["messages"][-1].content
    
    routing_context = f"""
        You are a routing agent. Your job is to determine the best memory source for answering the user's query.
        You must return only one of these responses: DIRECT, USE_SHORT_TERM, SUMMARIZE_TODAY, NEWS, SEND_EMAIL, CREATE_EVENT, CREATE_TASK, or NONE. 

        Use this logic:
        1. If the user is stating a fact (e.g., 'I live in New York', 'I am a student'), treat it as DIRECT.
        2. If the question includes recency indicators like ('did I just', 'did I recently', 'did I mention earlier'),
           or if it's about past facts without recent cues (e.g., 'What is my name?', 'Where do I live?') return USE_SHORT_TERM.
        3. If the user is asking for a summary of today's schedule, today's data, or anything related to
           today's activities (e.g., 'What's on my agenda today?', 'Can you summarize today's schedule?',
           'Send me today's summary', 'What do I have planned for today?'), return SUMMARIZE_TODAY.
        4. If the user is asking about news, current events, latest headlines, or specific news topics
           (e.g., 'What's happening in the world?', 'Tell me the latest news', 'What's going on in technology?',
           'Any breaking news about climate change?'), return NEWS.
        5. If the user is asking to send an email, message, or communication to someone, or if they're dictating
           an email (e.g., 'Send an email to John', 'Email the team about the meeting', 'Send a message to HR about my leave',
           'Send this to sarah@example.com', 'Draft an email about the project delay'), return SEND_EMAIL.
        6. If the user is asking to create a calendar event, schedule a meeting, or add something to their agenda
           (e.g., 'Schedule a meeting tomorrow', 'Add an event to my calendar', 'Create an appointment',
           'Set up a team meeting for Friday'), return CREATE_EVENT.
        7.  If the user is asking to create a task, add a to-do item, or remember something to do
           (e.g., 'Add a task to buy groceries', 'Remind me to call mom tomorrow', 'Create a to-do to finish the report',
           'Add finish homework to my tasks'), return CREATE_TASK.
        8. If the query is generic or unrelated to memory, return NONE.

        Examples:
        - 'I live in Bangalore' → DIRECT
        - 'I'm pursuing a master's in CS' → DIRECT
        - 'Did I just tell you my degree?' → USE_SHORT_TERM
        - 'Send me today's summary' → SUMMARIZE_TODAY
        - 'What's on my schedule for today?' → SUMMARIZE_TODAY 
        - 'What's the latest news?' → NEWS
        - 'Tell me about technology news' → NEWS
        - 'Any updates on the stock market?' → NEWS
        - 'Send an email to John@gmail.com that the project is ready to be shipped' → SEND_EMAIL
        - 'Draft a message to suk@gmail.com that I'll be late for the meeting' → SEND_EMAIL
        - 'Schedule a meeting with the team tomorrow' → CREATE_EVENT
        - 'Add a doctor's appointment to my calendar' → CREATE_EVENT
        - 'Remind me to submit my assignment by Friday' → CREATE_TASK
        - 'Create a to-do item for calling the dentist' → CREATE_TASK
        - 'Tell me a joke' → NONE

        User query: {message}
    """

    decision = ask_routing_agent(routing_context).strip().split()[0].upper()
    logger.info(f"🧭 Routing decision: {decision}")
    
    return {"routing_decision": decision}

async def direct_response_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a direct response without memory."""
    # Get the most recent message
    message = state["messages"][-1].content
    
    response = ask_groq(message)
    logger.info("📗 DIRECT → LLM called")
    
    if is_error(response):
        logger.error(f"❗ LLM error in DIRECT: {response}")
        response = "Sorry, I had trouble answering that. Could you please rephrase?"
    
    return {
        "response_text": response,
        "memory_used": "direct",
        "messages": state["messages"] + [AIMessage(content=response)]
    }

async def short_term_memory_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a response using short-term memory."""
    # Get the most recent message
    message = state["messages"][-1].content
    conversation_id = state.get("conversation_id", "default")
    
    memory = get_memory(conversation_id)
    if memory:
        context = "\n".join([f"{role.capitalize()}: {msg}" for role, msg in memory]) + f"\nUser: {message}"
        relevance_prompt = (
            f"You are a relevance evaluator. Return YES or NO only.\n"
            f"Does the following context help answer the user's question?\n\n"
            f"Context:\n{context}\n\nQuestion: {message}"
        )
        relevance = ask_routing_agent(relevance_prompt).strip().split()[0].upper()
        logger.info(f"📘 SHORT_TERM → Relevant: {relevance}")
        
        if relevance == "YES":
            response = ask_groq(context)
            if is_error(response):
                logger.error(f"❗ LLM error in SHORT_TERM: {response}")
                response = "Sorry, I had trouble answering that. Could you please rephrase?"
            
            return {
                "response_text": response,
                "memory_used": "short_term",
                "messages": state["messages"] + [AIMessage(content=response)]
            }
    
    # Fallback to direct if memory not useful
    logger.info("📙 SHORT_TERM → No relevant memory, falling back to direct.")
    return await direct_response_node(state)

async def no_memory_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a response without using memory."""
    # Get the most recent message
    message = state["messages"][-1].content
    
    logger.info("🔄 NONE → Answering fresh without memory.")
    context = "User asked something that has no relevant memory. Answer fresh.\n\nUser: " + message
    response = ask_groq(context)
    
    if is_error(response):
        logger.error(f"❗ LLM error in NONE case: {response}")
        response = "Sorry, I had trouble answering that. Could you please rephrase?"
    
    return {
        "response_text": response,
        "memory_used": "none",
        "messages": state["messages"] + [AIMessage(content=response)]
    }

async def fallback_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a fallback response when other methods fail."""
    # Get the most recent message
    message = state["messages"][-1].content
    
    logger.warning("⚠️ No response generated. Using fallback.")
    response = ask_groq(message)
    
    if is_error(response):
        logger.error(f"❗ Fallback also failed: {response}")
        response = "Sorry, something went wrong with the assistant."
    
    return {
        "response_text": response,
        "memory_used": "fallback",
        "messages": state["messages"] + [AIMessage(content=response)]
    }

async def update_memory_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Update memory with the conversation."""
    conversation_id = state.get("conversation_id", "default")
    
    # Get the last two messages (user and assistant)
    if len(state["messages"]) >= 2:
        user_message = state["messages"][-2].content
        assistant_message = state["messages"][-1].content
        
        add_to_memory(conversation_id, "user", user_message)
        add_to_memory(conversation_id, "assistant", assistant_message)
        add_to_qdrant(conversation_id, user_message)
        
        logger.info(f"✅ Final → Memory Updated: {conversation_id}")
    
    return {}

async def check_media_response_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Check if the response should be converted to a different media type."""
    # If there's no response text, skip this node
    if not state.get("response_text"):
        return {"response_media_type": "text"}
    
    response = state["response_text"]
    media_type = state.get("media_type")
    
    # Check if this should be an image
    tti_routing_prompt = f"""
        You are an intelligent router. The user or assistant has responded with:
        "{response}"
        Should this be treated as a prompt to generate an image? 
        Only return YES or NO.
        """
    
    is_tti = ask_routing_agent(tti_routing_prompt).strip().split()[0].upper() == "YES"
    
    if is_tti:
        return {"response_media_type": "image"}
    elif media_type == "audio":
        return {"response_media_type": "audio"}
    else:
        return {"response_media_type": "text"}

async def generate_image_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate an image based on the response."""
    response = state["response_text"]
    
    try:
        logger.info(f"🖌️ LLM router says generate image → invoking TTI for: {response}")
        tti = TextToImage()
        image_bytes = await tti.generate_image(response)
        logger.info("✅ TTI image generated successfully")
        
        return {"response_bytes": image_bytes}
    except Exception as e:
        logger.error(f"❗ TTI error: {e}")
        return {"response_media_type": "text"}  # Fall back to text

async def generate_speech_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate speech based on the response."""
    response = state["response_text"]
    
    logger.info("🔈 Detected original audio input — converting reply to speech...")
    tts = TextToSpeech()
    try:
        audio_bytes = await tts.synthesize(response)
        logger.info("✅ Audio synthesis complete")
        
        return {"response_bytes": audio_bytes}
    except Exception as e:
        logger.error(f"❗ TTS error: {e}")
        return {"response_media_type": "text"} 

async def summarize_today_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a summary of today's schedule from daily JSON data."""
    # Get the most recent message
    message = state["messages"][-1].content
    
    # Get today's date in the expected format (YYYY-MM-DD)
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Use the direct path that worked
    json_path = os.path.join("prefect", "data", f"{today}.json")
    
    logger.info(f"📅 Attempting to summarize data from: {json_path}")
    
    try:
        # Check if the file exists
        if not os.path.exists(json_path):
            logger.warning(f"❗ No data file found for today at {json_path}")
            response = f"I couldn't find any schedule data for today ({today}). The system looked for {json_path}, but it doesn't exist."
            return {
                "response_text": response,
                "memory_used": "none",
                "messages": state["messages"] + [AIMessage(content=response)]
            }
            
        # Read and parse the JSON data
        with open(json_path, 'r') as file:
            daily_data = json.load(file)
        
        # Create a prompt that includes the data for summarization
        summary_prompt = f"""
        Summarize the following data that includes emails from the last 24 hours, today's calendar events, and pending tasks. 
        
        Raw data:
        {json.dumps(daily_data, indent=2)}
        
        Guidelines:
        - Use simple bullet points (no markdown formatting)
        - Group information by category (emails, meetings, tasks)
        - Highlight urgent matters first
        - For emails: focus on sender, subject, and key action items
        - For calendar: focus on meeting times, participants, and topics
        - For tasks: focus on deadlines and priorities
        - Keep it concise and easy to scan
        - Use simple, direct language
        
        The user asked: "{message}"
        
        Provide a straightforward, easy-to-read summary using only simple text pointers.
        """
        
        # Generate the summary using the LLM
        response = ask_groq(summary_prompt)
        logger.info("📊 SUMMARIZE_TODAY → Generated summary from today's data")
        
        if is_error(response):
            logger.error(f"❗ LLM error in SUMMARIZE_TODAY: {response}")
            response = "Sorry, I had trouble summarizing today's data. Please try again later."
        
        return {
            "response_text": response,
            "memory_used": "summary",
            "messages": state["messages"] + [AIMessage(content=response)]
        }
        
    except Exception as e:
        logger.error(f"❗ Error summarizing today's data: {e}", exc_info=True)
        response = f"Sorry, I encountered an error while trying to access today's data: {str(e)}"
        return {
            "response_text": response,
            "memory_used": "none",
            "messages": state["messages"] + [AIMessage(content=response)]
        }
    

async def news_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch and process news based on user query."""
    # Get the most recent message
    message = state["messages"][-1].content
    
    # Extract parameters from user query
    logger.info(f"🗞️ Processing news request: {message}")
    
    # Use LLM to extract parameters from the query
    extraction_prompt = f"""
    Extract news search parameters from this query: "{message}"
    
    Available parameters:
    - country (2-letter code, e.g., 'us')
    - category (options: business, entertainment, general, health, science, sports, technology)
    - q (search keywords)
    
    Return a JSON object with these parameters. If a parameter is not mentioned or unclear, omit it.
    Only include parameters that are clearly specified or strongly implied in the query.
    """
    
    try:
        # Extract parameters using LLM
        params_response = ask_groq(extraction_prompt)
        logger.info(f"🔍 Extracted parameters: {params_response}")
        
        # Parse the parameters
        try:
            # Clean up the response to ensure it's valid JSON
            params_text = params_response.strip()
            if params_text.startswith("```json"):
                params_text = params_text.replace("```json", "", 1)
            if params_text.endswith("```"):
                params_text = params_text.rsplit("```", 1)[0]
            
            params = json.loads(params_text.strip())
        except json.JSONDecodeError:
            logger.error(f"❗ Failed to parse parameters JSON: {params_response}")
            # Fallback to manual extraction for common queries
            params = {}
            if any(term in message.lower() for term in ["business", "market", "stock", "economy"]):
                params["category"] = "business"
            elif any(term in message.lower() for term in ["entertainment", "celebrity", "movie", "film", "tv", "show"]):
                params["category"] = "entertainment"
            elif any(term in message.lower() for term in ["health", "medical", "covid", "disease"]):
                params["category"] = "health"
            elif any(term in message.lower() for term in ["science", "research", "discovery"]):
                params["category"] = "science"
            elif any(term in message.lower() for term in ["sports", "game", "match", "tournament"]):
                params["category"] = "sports"
            elif any(term in message.lower() for term in ["tech", "technology", "digital", "software", "hardware"]):
                params["category"] = "technology"
            
            # Default to general if no category was matched
            if not params:
                params["category"] = "general"
                
            # Extract country if mentioned
            if "us" in message.lower() or "america" in message.lower() or "united states" in message.lower():
                params["country"] = "us"
                
            # Extract search terms for the "q" parameter
            query_terms = []
            for term in ["about", "regarding", "on", "related to"]:
                if term in message.lower():
                    parts = message.lower().split(term, 1)
                    if len(parts) > 1:
                        query_terms.append(parts[1].strip())
            
            if query_terms:
                params["q"] = query_terms[0]
        
        # Set default values if needed
        if not params.get("country") and not params.get("category") and not params.get("q"):
            params["category"] = "general"
            if "us" in message.lower() or "america" in message.lower() or "united states" in message.lower():
                params["country"] = "us"
        
        # Add API key and default parameters
        params["apiKey"] = os.environ.get("NEWS_API_KEY", "your_api_key_here")
        params["pageSize"] = 5  # Limit to 5 articles for a concise summary
        
        # Make the API request
        logger.info(f"📡 Making news API request with parameters: {params}")
        news_response = requests.get("https://newsapi.org/v2/top-headlines", params=params)
        
        if news_response.status_code != 200:
            logger.error(f"❗ News API request failed: {news_response.status_code} - {news_response.text}")
            response = f"Sorry, I couldn't fetch the latest news at the moment. Please try again later."
            return {
                "response_text": response,
                "memory_used": "news",
                "messages": state["messages"] + [AIMessage(content=response)]
            }
        
        # Process the API response
        news_data = news_response.json()
        
        if news_data["status"] != "ok" or news_data["totalResults"] == 0:
            logger.warning(f"❗ No news articles found: {news_data}")
            response = f"I couldn't find any news articles matching your query. Would you like to try a different topic or category?"
            return {
                "response_text": response,
                "memory_used": "news",
                "messages": state["messages"] + [AIMessage(content=response)]
            }
        
        # Format the news data for summarization
        articles = news_data["articles"]
        formatted_articles = []
        
        for i, article in enumerate(articles):
            formatted_articles.append({
                "index": i + 1,
                "title": article.get("title", "No title"),
                "source": article.get("source", {}).get("name", "Unknown source"),
                "description": article.get("description", "No description available"),
                "url": article.get("url", ""),
                "publishedAt": article.get("publishedAt", "")
            })
        
        # Create a prompt for summarizing the news
        summary_prompt = f"""
        The user asked about news with this query: "{message}"
        
        Here are the top {len(formatted_articles)} news articles matching their query:
        
        {json.dumps(formatted_articles, indent=2)}
        
        Please provide a very concise summary of these news items in the form of brief bullet points:

            1. Start with a one-sentence overview of the main theme or topic
            2. Present 2-3 brief bullet points (one line each) highlighting the most important facts
            3. Each bullet point should be a simple, direct statement without elaborate details
            4. No need for transitions or connective text between points
            5. Keep everything extremely concise - the entire response should be short
            6. Mention sources only when absolutely necessary

        Remember to be conversational but extremely brief in your response.
        """
        
        # Generate the summary using the LLM
        response = ask_groq(summary_prompt)
        logger.info("📰 NEWS → Generated news summary")
        
        if is_error(response):
            logger.error(f"❗ LLM error in NEWS: {response}")
            response = "Sorry, I had trouble summarizing the news. Please try again later."
        
        return {
            "response_text": response,
            "memory_used": "news",
            "messages": state["messages"] + [AIMessage(content=response)]
        }
        
    except Exception as e:
        logger.error(f"❗ Error processing news request: {e}", exc_info=True)
        response = f"Sorry, I encountered an error while fetching news: {str(e)}"
        return {
            "response_text": response,
            "memory_used": "none",
            "messages": state["messages"] + [AIMessage(content=response)]
        }


async def send_email_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Process user query into email parameters and send an email."""
    # Get the most recent message
    message = state["messages"][-1].content
    
    # Use LLM to parse the message into email parameters
    email_context = f"""
    You are an email assistant that converts user requests into email parameters.
    Given the user's message, extract the email recipient(s), subject, and body.
    
    The output should be a valid JSON object with these fields:
    - "to": A list of email addresses (strings)
    - "subject": Email subject line (string)
    - "body": Email body (string)
    - "cc": Optional list of CC recipients (can be empty list)
    - "bcc": Optional list of BCC recipients (can be empty list)
    
    Rules:
    1. Always sign emails from "Sukruth Mothakapally". 
    2. If the user doesn't specify recipients, ask for recipients.
    3. If the user doesn't specify a subject, create a relevant subject.
    4. Format the email body professionally with proper greeting and signature.
    5. Return ONLY the JSON object, nothing else.
    
    Examples:
    "Send an email to john@example.com about the meeting tomorrow" →
    {{
      "to": ["john@example.com"],
      "subject": "Meeting Tomorrow",
      "body": "Dear John,\\n\\nI wanted to touch base about our meeting scheduled for tomorrow.\\n\\nBest regards,\\n[Your Name]",
      "cc": [],
      "bcc": []
    }}
    
    User message: {message}
    """
    
    try:
        # Get email parameters from LLM
        email_params_str = ask_groq(email_context)
        logger.info("📧 SEND_EMAIL → LLM parsed parameters")
        
        # If not a valid JSON, return an error
        try:
            email_params = json.loads(email_params_str)
            
            # Check for required fields
            if not email_params.get("to") or not isinstance(email_params["to"], list) or len(email_params["to"]) == 0:
                return {
                    "response_text": "I need at least one email recipient. Who would you like to send this email to?",
                    "memory_used": "email",
                    "messages": state["messages"] + [AIMessage(content="I need at least one email recipient. Who would you like to send this email to?")]
                }
                
            # Prepare the request to the email API
            from server.services.google import google_service
            
            message_id = google_service.send_email(
                to=email_params.get("to", []),
                subject=email_params.get("subject", ""),
                body=email_params.get("body", ""),
                cc=email_params.get("cc", []),
                bcc=email_params.get("bcc", [])
            )

            logger.info(f"✅ Email sent successfully with ID: {message_id}")
            
            # Create success response
            recipients = ", ".join(email_params.get("to", []))
            response = f"✅ Email sent successfully to {recipients}!\n\nSubject: {email_params.get('subject', '')}"
            
            return {
                "response_text": response,
                "memory_used": "email",
                "messages": state["messages"] + [AIMessage(content=response)]
            }
            
        except json.JSONDecodeError:
            logger.error(f"❗ Failed to parse email parameters: {email_params_str}")
            return {
                "response_text": "I had trouble understanding your email request. Please provide clear details about who to send the email to and what it should contain.",
                "memory_used": "email",
                "messages": state["messages"] + [AIMessage(content="I had trouble understanding your email request. Please provide clear details about who to send the email to and what it should contain.")]
            }
            
    except Exception as e:
        logger.error(f"❗ Error in SEND_EMAIL: {str(e)}")
        return {
            "response_text": f"Sorry, I couldn't send the email: {str(e)}",
            "memory_used": "email",
            "messages": state["messages"] + [AIMessage(content=f"Sorry, I couldn't send the email: {str(e)}")]
        }


async def calendar_event_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Process user query into calendar event parameters and create an event."""
    # Get the most recent message
    message = state["messages"][-1].content
    
    # Use LLM to parse the message into event parameters
    calendar_context = f"""
        You are a calendar assistant. Convert the user's request into event parameters as a valid JSON with:
        - "summary": Event title (required)
        - "location": Event location (optional)
        - "description": Event details (optional)
        - "start_time": Start time in ISO format (YYYY-MM-DDTHH:MM:SSZ) (required)
        - "end_time": End time in ISO format (YYYY-MM-DDTHH:MM:SSZ) (required)
        - "attendees": List of email addresses (optional)
        - "calendar_id": "primary" (always use this value)

        Use "Z" suffix for times to indicate UTC timezone. Infer reasonable duration if end time not specified.
        Return ONLY the JSON object.

        Example:
        "Schedule a team meeting tomorrow at 2pm" →
        {{
        "summary": "Team Meeting",
        "location": "",
        "description": "Regular team meeting",
        "start_time": "2025-05-08T14:00:00Z",
        "end_time": "2025-05-08T15:00:00Z", 
        "attendees": [],
        "calendar_id": "primary"
        }}

        User message: {message}
        """
    
    try:
        # Get event parameters from LLM
        event_params_str = ask_groq(calendar_context)
        logger.info("📅 CREATE_EVENT → LLM parsed parameters")
        
        # Parse the JSON parameters
        try:
            event_params = json.loads(event_params_str)
            
            # Check for required fields
            required_fields = ["summary", "start_time", "end_time"]
            missing_fields = [field for field in required_fields if not event_params.get(field)]
            
            if missing_fields:
                missing_str = ", ".join(missing_fields)
                return {
                    "response_text": f"I need more information to create this event. Please provide {missing_str}.",
                    "memory_used": "calendar",
                    "messages": state["messages"] + [AIMessage(content=f"I need more information to create this event. Please provide {missing_str}.")]
                }
                
            # Parse datetime strings to Python datetime objects
            from datetime import datetime
            start_time = datetime.fromisoformat(event_params["start_time"].replace("Z", "+00:00"))
            end_time = datetime.fromisoformat(event_params["end_time"].replace("Z", "+00:00"))
            
            # Prepare the request to the calendar API
            from server.services.google import google_service
            
            event_id = google_service.create_calendar_event(
                summary=event_params["summary"],
                start_time=start_time,
                end_time=end_time,
                location=event_params.get("location", ""),
                description=event_params.get("description", ""),
                attendees=event_params.get("attendees", []),
                calendar_id="primary"
            )
            
            # Log the event ID for troubleshooting
            logger.info(f"✅ Calendar event created successfully with ID: {event_id}")
            
            # Format start time for user-friendly response
            start_time_str = start_time.strftime("%A, %B %d at %I:%M %p")
            
            # Create success response
            response = f"✅ Event created successfully!\n\n📌 {event_params['summary']}\n🕒 {start_time_str}"
            
            if event_params.get("location"):
                response += f"\n📍 {event_params['location']}"
                
            if event_params.get("attendees") and len(event_params["attendees"]) > 0:
                attendees_str = ", ".join(event_params["attendees"])
                response += f"\n👥 Attendees: {attendees_str}"
            
            return {
                "response_text": response,
                "memory_used": "calendar",
                "messages": state["messages"] + [AIMessage(content=response)],
                "calendar_event_id": event_id
            }
            
        except json.JSONDecodeError:
            logger.error(f"❗ Failed to parse event parameters: {event_params_str}")
            return {
                "response_text": "I had trouble understanding your event request. Please provide clear details about the event title, time, and any other information.",
                "memory_used": "calendar",
                "messages": state["messages"] + [AIMessage(content="I had trouble understanding your event request. Please provide clear details about the event title, time, and any other information.")]
            }
            
    except Exception as e:
        logger.error(f"❗ Error in CREATE_EVENT: {str(e)}")
        return {
            "response_text": f"Sorry, I couldn't create the calendar event: {str(e)}",
            "memory_used": "calendar",
            "messages": state["messages"] + [AIMessage(content=f"Sorry, I couldn't create the calendar event: {str(e)}")]
        }
    

async def task_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Process user query into task parameters and create a task."""
    # Get the most recent message
    message = state["messages"][-1].content
    
    # Use LLM to parse the message into task parameters
    task_context = f"""
        You are a task assistant. Convert the user's request into task parameters as a valid JSON with:
        - "title": Task title (required)
        - "notes": Additional details (optional)
        - "due_date": Due date in ISO format (YYYY-MM-DDT00:00:00Z) (optional)

        Return ONLY the JSON object.

        Example:
        "Add a task to finish the report by next Friday" →
        {{
        "title": "Finish the report",
        "notes": "Complete and submit report",
        "due_date": "2025-05-09T00:00:00Z"
        }}

        User message: {message}
        """
    
    try:
        # Get task parameters from LLM
        task_params_str = ask_groq(task_context)
        logger.info("✅ CREATE_TASK → LLM parsed parameters")
        
        # Parse the JSON parameters
        try:
            task_params = json.loads(task_params_str)
            
            # Check for required fields
            if not task_params.get("title"):
                return {
                    "response_text": "I need a task title to create this task. What would you like me to add to your task list?",
                    "memory_used": "task",
                    "messages": state["messages"] + [AIMessage(content="I need a task title to create this task. What would you like me to add to your task list?")]
                }
                
            # Parse due_date if provided
            due_date = None
            if task_params.get("due_date"):
                from datetime import datetime
                due_date = datetime.fromisoformat(task_params["due_date"].replace("Z", "+00:00"))
            
            # Prepare the request to the tasks API
            from server.services.google import google_service
            
            task_id = google_service.create_task(
                title=task_params["title"],
                notes=task_params.get("notes", ""),
                due_date=due_date,
                task_list_id=None  # Let the service find the default list
            )
            
            # Log the task ID for troubleshooting
            logger.info(f"✅ Task created successfully with ID: {task_id}")
            
            # Create success response
            response = f"✅ Task added successfully: \"{task_params['title']}\""
            
            if due_date:
                due_date_str = due_date.strftime("%A, %B %d")
                response += f"\n📅 Due: {due_date_str}"
                
            if task_params.get("notes"):
                response += f"\n📝 Notes: {task_params['notes']}"
            
            return {
                "response_text": response,
                "memory_used": "task",
                "messages": state["messages"] + [AIMessage(content=response)],
                "task_id": task_id
            }
            
        except json.JSONDecodeError:
            logger.error(f"❗ Failed to parse task parameters: {task_params_str}")
            return {
                "response_text": "I had trouble understanding your task request. Please provide a clear task title and any due date or notes you'd like to include.",
                "memory_used": "task",
                "messages": state["messages"] + [AIMessage(content="I had trouble understanding your task request. Please provide a clear task title and any due date or notes you'd like to include.")]
            }
            
    except Exception as e:
        logger.error(f"❗ Error in CREATE_TASK: {str(e)}")
        return {
            "response_text": f"Sorry, I couldn't create the task: {str(e)}",
            "memory_used": "task",
            "messages": state["messages"] + [AIMessage(content=f"Sorry, I couldn't create the task: {str(e)}")]
        }