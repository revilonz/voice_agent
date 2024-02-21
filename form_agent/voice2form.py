from flask import Flask, Response, current_app, request, jsonify, send_file, url_for, render_template
from flask_cors import CORS
from openai import OpenAI
from pydub import AudioSegment
import io
import os
from dotenv import load_dotenv
import json
from bs4 import BeautifulSoup
import time
import json
import tempfile

def show_json(obj):
    # Convert the object to a JSON string and print it
    print(json.dumps(json.loads(obj.model_dump_json()), indent=4))

load_dotenv()
OpenAI.api_key = os.environ.get("OPENAI_API_KEY")
assistant_id = os.environ.get("ASSISTANT_ID")
client = OpenAI() 

app = Flask(__name__)
CORS(app)

# Deleting and creating a new thread
def save_thread_id(thread_id, file_path='.form_agent/static/thread_id.txt'):
    with open(file_path, 'w') as file:
        file.write(thread_id)
    print("\n THREAD: Saved thread ID to file.")

def read_thread_id(file_path='form_agent/static/thread_id.txt'):
    try:
        with open(file_path, 'r') as file:
            return file.read().strip()
    except FileNotFoundError:
        print("\n THREAD: Thread ID file not found.")
        return None

def create_and_save_thread():
    old_thread_id = read_thread_id()
    if old_thread_id:
        try:
            client.beta.threads.delete(old_thread_id)
            print("\n THREAD: Deleted old thread")
        except Exception as e:
            print(f" THREAD: Error deleting old thread: {e}")
    
    thread = client.beta.threads.create()
    new_thread_id = thread.id
    print("\n THREAD: Created new thread:", new_thread_id)
    save_thread_id(new_thread_id)

def save_arguments_to_temp_file(arguments):
    with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.json', prefix='arguments_', dir='./',) as tmpfile:
        json.dump(arguments, tmpfile)
        return tmpfile.name

@app.route('/')
def index():
    return render_template('index.html')

# OPEN AI QUERIES 

create_and_save_thread()

# Query GPT4
def query_gtp4(content, system_prompt):
    prompt = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content}
    ]
    print("\n QUERY_GPT4: Prompt:", prompt)
    response = client.chat.completions.create(
        model="gpt-4-1106-preview",
        messages=prompt
    )
    print("\n QUERY_GPT4: Response:", response.choices[0].message.content)
    return response.choices[0].message.content

# Convert text to speech
def text2speech(text):
    print("\n TEXT2SPEECH: Starting text-to-speech conversion...")

    # Create the TTS request
    tts_response = client.audio.speech.create(
        model="tts-1",
        voice="fable",
        input=text
    )
    audio_data = tts_response.content

    # Define the path for the audio file
    audio_filename = "audio.mp3"
    audio_filepath = os.path.join(current_app.root_path, 'static', audio_filename)
    print(f"\n TEXT2SPEECH: Preparing to save audio file to: {audio_filepath}")

    # Write the audio data to a file
    with open(audio_filepath, 'wb') as audio_file:
        audio_file.write(audio_data)
        print(f"\n TEXT2SPEECH: Successfully saved audio file at: {audio_filepath}")

    # Generate the URL for the saved audio file
    timestamp = int(time.time())
    audio_url = f'/static/{audio_filename}?v={timestamp}'
    print(f"\n TEXT2SPEECH: Audio file is accessible at: {audio_url}")
    # Return the URL
    return audio_url

# Convert recorded audio to text
def transcribe_audio():
    audio_file = request.files['audio']
    sound = AudioSegment.from_file_using_temporary_files(io.BytesIO(audio_file.read()))
    sound.export(".form_agent/static/temp.wav", format="wav")
    print("\n TRANSCRIBE_AUDIO:  Transcribing audio ")
    # Transcribe audio using Whisper
    with open(".form_agent/static/temp.wav", "rb") as audio_file:
        transcription = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
    transcribed_text = transcription.text
    return transcribed_text

def save_arguments_to_temp_file(arguments):
    file_path = './form_agent/static/arguments.json'
    with open(file_path, 'w') as tmpfile:
        json.dump(arguments, tmpfile)
        print("\n ARGUMENTS: Saving to file ")
        return tmpfile.name

def add_message(text):
    print("\n ADD_MESSAGE: add_message function started ")
    assistant_id = os.environ.get("ASSISTANT_ID")
    assistant_thread_id = read_thread_id()
    arguments_file_path = './form_agent/static/arguments.json'

    message = client.beta.threads.messages.create(
        thread_id=assistant_thread_id, role="user", content=text
    )
    print("\n ADD_MESSAGE: message added ")

    run = client.beta.threads.runs.create(
        thread_id=assistant_thread_id,
        assistant_id=assistant_id,
    )
    print("\n ADD_MESSAGE: run started ")
    tool_outputs = []
    arguments = None
    while True:
        run = client.beta.threads.runs.retrieve(thread_id=assistant_thread_id, run_id=run.id)
        if run.status in ["queued", "in_progress"]:
            time.sleep(1)
            print(run.status)
            continue
        elif run.status == "requires_action":
            assistant_tool_request = run.required_action.submit_tool_outputs.tool_calls
            print(f'\n ADD_MESSAGE: Assistant requests {len(assistant_tool_request)} TOOLS:')
            print(assistant_tool_request)
            for tool_call in assistant_tool_request:
                tool_call_id = tool_call.id
                name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                print(f'\n ADD_MESSAGE: Assistant requested {name}({arguments})')
                output = json.dumps(arguments)
                with open(arguments_file_path, 'w') as file:
                    json.dump(arguments, file)
                tool_outputs.append({"tool_call_id": tool_call_id, "output": output})
                print(f'\n ADD_MESSAGE: Returning {tool_outputs}')
                client.beta.threads.runs.submit_tool_outputs(
                    thread_id=assistant_thread_id,
                    run_id=run.id,
                    tool_outputs=tool_outputs,
                )
            print(run.status)
            continue
        elif run.status == "completed":
            break

    messages = client.beta.threads.messages.list(thread_id=assistant_thread_id, order="asc", after=message.id)
    try:
        assistant_message = messages.data[0].content[0].text.value
        print("\n ADD_MESSAGE: This is the assistant_message:", assistant_message)
    except (IndexError, KeyError):
        print("\n ADD_MESSAGE: Error extracting assistant message")
        assistant_message = None
    return assistant_message

@app.route('/generate-form-summary', methods=['POST'])

def generate_form_summary():
    print("\n GENERATE FORM: Extracting fields")
    form_html = request.form['htmlContent']
    form_heading = request.form.get('formHeading', '') 
    soup = BeautifulSoup(form_html, 'html.parser')
    fields = []
    for input_tag in soup.find_all('input'):
        field_id = input_tag.get('id')
        field_name = input_tag.get('name') 
        if field_id and field_name: 
            fields.append({'id': field_id, 'name': field_name})
    content = form_heading + " " + " ".join([f"{field['id']} ({field['name']})" for field in fields if 'id' in field and 'name' in field])
    system_prompt = "\nSummarize the purpose of this form in 20 words based on the following details and start with 'This form is ...':"
    print("\n GENERATE FORM: System prompt:", system_prompt)
    text = query_gtp4(content, system_prompt)
    audio_url = text2speech(text)
    generate_form_response = jsonify({"text": text, "audioUrl": audio_url, "fields": fields})
    print("\n GENERATE FORM: Sending response to client:", generate_form_response)
    return generate_form_response

@app.route('/start_assistant', methods=['POST'])

def start_assistant():
    data = request.get_json()
    text = data.get('text', '')
    fields = data.get('fields', [])
    print("\n  START_ASSISTANT: This is the start_assistant text:", text)
    print("\n START_ASSISTANT: Form fields received:", fields)

    if not text:
        return jsonify({"error": "Text is required"}), 400

    fields_str = ', '.join([f"{field['id']}: {field['name']}" for field in fields if field['id'] is not None])
    message_to_assistant = f"{text}. Fields: {fields_str}"

    print("\n START_ASSISTANT: Message to assistant:", message_to_assistant)

    assistant_message= add_message(message_to_assistant)
    print("\n START_ASSISTANT: Add message returned to start_assistant:", assistant_message)
    audio_url = text2speech(assistant_message)
    print("\n START_ASSISTANT: This is the assistant audio url", audio_url)
    start_assistant_response = jsonify({"audioUrl": audio_url})
    print("\n START_ASSISTANT: Completed:", start_assistant_response)
    return start_assistant_response

def process_assistant_response(text):
    if "submitted" in text.lower():
        return True
    else:
        return False

# Convert text2audio
@app.route('/transcribe', methods=['POST'])

def transcribe_and_respond():
    print("Received request:")
    print("\n TRANSCRIBE_AND_RESPOND: Sending audio to be transcribed ...")
    transcribed_text = transcribe_audio()

    print("\n TRANSCRIBE_AND_RESPOND: This is the transcribed text:", transcribed_text)

    assistant_message = add_message(transcribed_text)

    is_submit = process_assistant_response(assistant_message)
    print("\n TRANSCRIBE_AND_RESPOND: Assistant process completed:", is_submit)

    audio_url = text2speech(assistant_message)
    print("This is the assistant audio url", audio_url)

    arguments_file_path = './form_agent/static/arguments.json'
    with open(arguments_file_path, 'r') as file:
        arguments = json.load(file)
    print(f"\n TRANSCRIBE_AND_RESPOND: formFields: {arguments}")

    return jsonify({"audioUrl": audio_url, "isSubmit": is_submit, "formFields": arguments})

if __name__ == "__main__":
    app.run(debug=True)