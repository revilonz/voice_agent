# How it works

_The tech: Built using a flask app, python server and a javascript client. Note, I am not a full-stack dev and have no desire to become one. This was my first full website build and I learned a lot about JS!_

After the page loads, the HTML of the first form on the page is sent to the server to extract the form fields. This is then added to a prompt to OpenAI GPT4 API for summarisation:
```
Prompt: [{'role': 'system', 'content': "\nSummarize the purpose of this form in 20 words based on the following details and start with 'This form is ...':"}, {'role': 'user', 'content': 'Personal Details Form name (name) nationality (nationality) email (email)'}]

Response: This form is designed to collect basic personal information, including name, nationality, and email address from individuals.
```
This response is sent to the Text To Speech (TTS) API which returns audio that is saved and sent back to the client (browser) and is automatically played. This acts as the introduction to the form, its purpose and the type of fields required.

Next, the response is also sent to the OpenAI custom assistant which has been configured to help someone complete a form using their voice: 

_You are a personal assistant for users wanting to complete website forms. Users are using their voice not typing entries. You prompt for data asking for one or two questions at a time to populate all of the available fields and parse the user responses accordingly keeping memory of these. Use phrases like "Please say..". If any fields are blank you will prompt for that data. Check the details with the user. Format user responses by capitalising names if not and ensure email addresses are valid, as the user is not typing you need to listen for the word 'at' and change this automatically to a @ and never automatically put www. in front of an email address. When they've confirmed they are all correct, return 'Thanks, your form will now be submitted'. Note: Once the user details are available you should always call the function ‘get_user_data’. This function is an essential step to ensure that the form fields are populated with user provided data and is structured as json._

This step requires an Assistant ID, the creation of a Thread (ID) and a Message to be passed into both as a 'run'. 
```
This is the assistant_message: Let's start filling out the form with your basic personal information. 

Please say your full name.
```
The assistant has two functions available which it can choose to call; 
1. Extract form fields and create them into a JSON object {"id":"name"},
2. Populate the JSON object with the user's data. This ensures the data returned to the form is structured in a way that can be directly used to populate it.
```
Returning [{'tool_call_id': 'call_iAAhy3vG0PiQpxqUrEXF6ToP', 'output': '{"form_fields": [{"id": "name", "name": "Name"}, {"id": "nationality", "name": "Nationality"}, {"id": "email", "name": "Email Address"}]}'}]
```
The assistant's initial reply is then retrieved and sent again to the TTS function that plays it in the user's browser. This prompts for a reply from the user and the browser starts recording audio which is handled by the JavaScript and sent to the server.

The user's audio is transcribed to text using the OpenAI Speech to Text  (STT) API and is then routed to the assistant as a message, another run is triggered and the next assistant's reply is retrieved and returned by way of the TTS function back to the browser for playing.
```
TRANSCRIBE_AND_RESPOND: This is the transcribed text: Olly Barrett!
ADD_MESSAGE: add_message run started 
STATUS: in_progress
ADD_MESSAGE: This is the assistant_message: Great! Now, please tell me your nationality.
```
This continues in a loop until the assistant believes it has obtained all of the form data when it reads a summary for confirmation by the user. 
```
Assistant_message: Here are the details you've provided:
- Name: Olly Barrett
- Nationality: British
- Email: olly@barrett.com
```
Please confirm if all these details are correct.
At any time the user can request something is corrected and the assistant will update its knowledge, otherwise when the user confirms the agent returns with _"This is the assistant_message: Thanks, your form will now be submitted"_. This then breaks the loop and the stored values from the second assistant function are sent to the client and the form is populated.
```
{"form_fields": [{"id": "name", "value": "Olly Barrett"}, {"id": "nationality", "value": "British"}, {"id": "email", "value": "olly@barrett.com"}]}
```
