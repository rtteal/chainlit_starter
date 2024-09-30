from dotenv import load_dotenv
import chainlit as cl
from movie_functions import get_now_playing_movies, get_showtimes
import json

load_dotenv()

# Note: If switching to LangSmith, uncomment the following, and replace @observe with @traceable
# from langsmith.wrappers import wrap_openai
# from langsmith import traceable
# client = wrap_openai(openai.AsyncClient())

from langfuse.decorators import observe
from langfuse.openai import AsyncOpenAI
 
client = AsyncOpenAI()

gen_kwargs = {
    "model": "gpt-4o",
    "temperature": 0.2,
    "max_tokens": 500
}

SYSTEM_PROMPT = """\
You are a helpful assistant that can sometimes answer with a list of movies. If you
need a list of movies, generate a function call, as shown below.

You can also get showtimes for a user if they ask for it by calling get_showtimes(title, location).

You can help users buy tickets by calling buy_ticket(theater, movie, showtime).

Please only generate valid JSON when calling functions. No preamble.

If No showtimes found report that to the user.

If you encounter errors, report the issue to the user.

If the user doesn't provide a location, check the history for a location. If no location is found, ask the user for their location.

{
    "function_name": "get_now_playing_movies",
    "arguments": {
        "location": "Chicago, IL",
        "title": "The Super Mario Bros. Movie"
    },
    "rationale": "Explain why you are calling the function"
}

{
    "function_name": "buy_ticket",
    "arguments": {
        "theater": "AMC River East 21",
        "movie": "The Super Mario Bros. Movie",
        "showtime": "7:00 PM"
    },
    "rationale": "User wants to purchase a ticket"
}

{
    "function_name": "confirm_ticket_purchase",
    "arguments": {
        "theater": "AMC River East 21",
        "movie": "The Super Mario Bros. Movie",
        "showtime": "7:00 PM"
    },
    "rationale": "Confirming ticket purchase details with the user"
}
"""

@observe
@cl.on_chat_start
def on_chat_start():    
    message_history = [{"role": "system", "content": SYSTEM_PROMPT}]
    cl.user_session.set("message_history", message_history)

@observe
async def generate_response(client, message_history, gen_kwargs):
    response_message = cl.Message(content="")
    await response_message.send()

    stream = await client.chat.completions.create(messages=message_history, stream=True, **gen_kwargs)
    async for part in stream:
        if token := part.choices[0].delta.content or "":
            await response_message.stream_token(token)
    
    await response_message.update()

    return response_message

@cl.on_message
@observe
async def on_message(message: cl.Message):
    message_history = cl.user_session.get("message_history", [])
    message_history.append({"role": "user", "content": message.content})
    
    x = True
    while x:
        response_message = await generate_response(client, message_history, gen_kwargs)

        # Check if the response is a function call
        if response_message.content.strip().startswith('{'):
            try:
                # Parse the JSON object
                function_call = json.loads(response_message.content.strip())
                
                # Check if it's a valid function call
                if "function_name" in function_call:
                    function_name = function_call["function_name"]
                    rationale = function_call.get("rationale", "") if "rationale" in function_call else ""
                    arguments = function_call.get("arguments", {})
                    # Handle the function call
                    if function_name == "get_now_playing_movies":
                        movies = get_now_playing_movies()
                        message_history.append({"role": "system", "content": f"Function call rationale: {rationale}\n\n{movies}"})
                        
                        # Generate a new response based on the function call result
                        response_message = await generate_response(client, message_history, gen_kwargs)
                    elif function_name == "get_showtimes":
                        print(f"get_showtimes called with arguments: {arguments}")
                        showtimes = get_showtimes(arguments["title"], arguments["location"])
                        message_history.append({"role": "system", "content": f"Function call rationale: {rationale}\n\n{showtimes}"})
                        response_message = await generate_response(client, message_history, gen_kwargs)
                    elif function_name == "buy_ticket":
                        print(f"buy_ticket called with arguments: {arguments}")
                        # Add a system message to confirm the ticket details with the user
                        confirmation_message = f"Please confirm the following ticket details:\nTheater: {arguments['theater']}\nMovie: {arguments['movie']}\nShowtime: {arguments['showtime']}\nAsk the user if they want to proceed with the purchase."
                        message_history.append({"role": "system", "content": confirmation_message})
                        response_message = await generate_response(client, message_history, gen_kwargs)
                    elif function_name == "confirm_ticket_purchase":
                        # This function will be implemented later for actual ticket confirmation
                        pass
                    else:
                        # Handle unknown function calls
                        error_message = f"Unknown function: {function_name}"
                        message_history.append({"role": "system", "content": error_message})
                        response_message = await cl.Message(content=error_message).send()
                else:
                    # Handle invalid function call format
                    error_message = "Invalid function call format"
                    message_history.append({"role": "system", "content": error_message})
                    response_message = await cl.Message(content=error_message).send()
            except json.JSONDecodeError:
                # If it's not valid JSON, treat it as a normal message
                x = False
                pass
        else:
            x = False

        message_history.append({"role": "assistant", "content": response_message.content})
        cl.user_session.set("message_history", message_history)

if __name__ == "__main__":
    cl.main()