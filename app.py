import os
from flask import Flask, render_template, request, jsonify
import requests  # For API calls to Mistral
from pdf2image import convert_from_bytes
import pytesseract
from PIL import Image
import io
import fitz  # PyMuPDF

app = Flask(__name__)

# Mistral AI API configuration
MISTRAL_API_KEY = "your_api_key"  # Replace with your actual API key
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"

def call_mistral_api(prompt, model="mistral-large-latest"):
    """Call Mistral AI API with the provided prompt."""
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 1024
    }
    
    try:
        response = requests.post(MISTRAL_API_URL, headers=headers, json=data)
        response.raise_for_status()  # Raise exception for HTTP errors
        
        result = response.json()
        return result['choices'][0]['message']['content']
    except Exception as e:
        raise Exception(f"Mistral API error: {str(e)}")

def extract_text_from_pdf(pdf_bytes):
    """Extract text from PDF using PyMuPDF."""
    text = ""
    try:
        # Open the PDF from memory
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        # Extract text from each page
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text += page.get_text()
        
        doc.close()  # Properly close the document
        return text
    except Exception as e:
        return f"Error extracting text from PDF: {str(e)}"

def extract_text_from_image(image_bytes):
    """Extract text from image using pytesseract OCR."""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image)
        return text
    except Exception as e:
        return f"Error extracting text from image: {str(e)}"

def process_pdf_with_ocr(pdf_bytes):
    """Process PDF with OCR if regular text extraction yields limited results."""
    # First try regular text extraction
    text = extract_text_from_pdf(pdf_bytes)
    
    # If extracted text is too short, try OCR
    if len(text.strip()) < 100 and not text.startswith("Error"):
        try:
            # Convert PDF to images
            images = convert_from_bytes(pdf_bytes)
            ocr_text = ""
            
            # Apply OCR to each page
            for image in images:
                ocr_text += pytesseract.image_to_string(image)
                
            return ocr_text if ocr_text.strip() else text
        except Exception as e:
            return f"Error processing PDF with OCR: {str(e)}"
    
    return text

def get_prompt_for_query_type(query_type, document_text=None):
    """Generate appropriate prompt based on query type."""
    if query_type == "medical":
        base_prompt = """You are a medical assistant AI. Provide helpful information about medical conditions, treatments, and recommendations. 
        Note that your responses should include appropriate disclaimers about consulting healthcare professionals.
        """
        if document_text:
            return base_prompt + f"\n\nAnalyze the following medical document and provide insights: {document_text}"
        return base_prompt
    
    elif query_type == "legal":
        base_prompt = """You are a legal assistant AI. Provide helpful information about legal concepts, documents, and processes.
        Include appropriate disclaimers about consulting qualified legal professionals for specific advice.
        """
        if document_text:
            return base_prompt + f"\n\nAnalyze the following legal document and provide insights: {document_text}"
        return base_prompt
    
    return "You are a helpful assistant. Please provide information on the following query:"

def create_templates_directory():
    # Create templates directory if it doesn't exist
    import os
    if not os.path.exists("templates"):
        os.makedirs("templates")
        
    with open("templates/index.html", "w") as f:
        f.write("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Medical & Legal Assistant</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f8fa;
            margin: 0;
            padding: 0;
        }
        
        .chat-container {
            max-width: 1200px;
            margin: 30px auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .chat-header {
            background: linear-gradient(135deg, #4b6cb7, #182848);
            color: white;
            padding: 20px;
            text-align: center;
        }
        
        .chat-messages {
            height: 400px;
            overflow-y: auto;
            padding: 20px;
            background-color: #f9f9f9;
        }
        
        .message {
            margin-bottom: 15px;
            padding: 12px 18px;
            border-radius: 18px;
            max-width: 80%;
            position: relative;
            line-height: 1.5;
        }
        
        .user-message {
            background-color: #e3f2fd;
            color: #0d47a1;
            margin-left: auto;
            border-bottom-right-radius: 5px;
        }
        
        .bot-message {
            background-color: #ffffff;
            color: #333;
            border: 1px solid #e0e0e0;
            border-bottom-left-radius: 5px;
        }
        
        .chat-input {
            padding: 20px;
            background-color: #fff;
            border-top: 1px solid #eaeaea;
        }
        
        .query-type-selector {
            margin-bottom: 15px;
        }
        
        .file-input-container {
            margin-bottom: 15px;
        }
        
        .typing-indicator {
            display: none;
            padding: 10px;
            background-color: #f0f0f0;
            border-radius: 10px;
            margin-bottom: 10px;
        }
        
        .typing-indicator span {
            height: 10px;
            width: 10px;
            background-color: #333;
            border-radius: 50%;
            display: inline-block;
            margin: 0 2px;
            animation: bounce 1.2s infinite;
        }
        
        .typing-indicator span:nth-child(2) {
            animation-delay: 0.2s;
        }
        
        .typing-indicator span:nth-child(3) {
            animation-delay: 0.4s;
        }
        
        @keyframes bounce {
            0%, 80%, 100% { transform: translateY(0); }
            40% { transform: translateY(-10px); }
        }
        
        .disclaimer {
            font-size: 12px;
            color: #666;
            text-align: center;
            padding: 10px;
            border-top: 1px solid #eee;
        }
        
        /* Additional features styling */
        .feature-toggle {
            margin-bottom: 15px;
        }
        
        .theme-selector {
            margin-bottom: 15px;
        }
        
        .dark-mode {
            background-color: #333 !important;
            color: #f0f0f0 !important;
        }
        
        .dark-mode .chat-container {
            background-color: #444;
        }
        
        .dark-mode .chat-messages {
            background-color: #555;
        }
        
        .dark-mode .user-message {
            background-color: #2c5282;
            color: #e3f2fd;
        }
        
        .dark-mode .bot-message {
            background-color: #666;
            color: #fff;
            border-color: #777;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="chat-container">
            <div class="chat-header">
                <h1>Medical & Legal Assistant</h1>
                <p>Ask medical or legal questions and upload documents for analysis</p>
            </div>
            
            <div class="row p-3">
                <div class="col-md-4">
                    <div class="card mb-3">
                        <div class="card-header bg-primary text-white">
                            Settings
                        </div>
                        <div class="card-body">
                            <div class="query-type-selector mb-3">
                                <label class="form-label">Query Type:</label>
                                <select id="query-type" class="form-select">
                                    <option value="medical">Medical</option>
                                    <option value="legal">Legal</option>
                                    <option value="general">General</option>
                                </select>
                            </div>
                            
                            <div class="feature-toggle mb-3">
                                <label class="form-label">Features:</label>
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="text-to-speech">
                                    <label class="form-check-label" for="text-to-speech">
                                        Text-to-Speech
                                    </label>
                                </div>
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="enable-history">
                                    <label class="form-check-label" for="enable-history">
                                        Save Chat History
                                    </label>
                                </div>
                            </div>
                            
                            <div class="theme-selector">
                                <label class="form-label">Theme:</label>
                                <select id="theme-selector" class="form-select">
                                    <option value="light">Light</option>
                                    <option value="dark">Dark</option>
                                </select>
                            </div>
                            
                            <button id="clear-chat" class="btn btn-danger w-100 mt-3">Clear Chat</button>
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-header bg-info text-white">
                            Document Upload
                        </div>
                        <div class="card-body">
                            <div class="file-input-container">
                                <label for="document-upload" class="form-label">Upload PDF or Image:</label>
                                <input type="file" id="document-upload" class="form-control" accept=".pdf,.jpg,.jpeg,.png">
                            </div>
                            <div id="upload-preview" class="mt-2 d-none">
                                <p class="text-success">Document ready for analysis</p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-8">
                    <div class="chat-messages" id="chat-messages">
                        <div class="message bot-message">
                            Hello! I'm your medical and legal assistant. You can ask me questions, upload documents for analysis, or both. How can I help you today?
                        </div>
                    </div>
                    
                    <div class="typing-indicator" id="typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                    </div>
                    
                    <div class="chat-input">
                        <form id="chat-form">
                            <div class="input-group">
                                <input type="text" id="user-input" class="form-control" placeholder="Type your question here...">
                                <button type="submit" class="btn btn-primary">Send</button>
                            </div>
                        </form>
                    </div>
                    
                    <div class="disclaimer">
                        Disclaimer: This AI assistant provides information for educational purposes only. 
                        For medical queries, always consult with qualified healthcare professionals. 
                        For legal matters, consult with licensed attorneys.
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const chatForm = document.getElementById('chat-form');
            const userInput = document.getElementById('user-input');
            const chatMessages = document.getElementById('chat-messages');
            const queryType = document.getElementById('query-type');
            const documentUpload = document.getElementById('document-upload');
            const uploadPreview = document.getElementById('upload-preview');
            const typingIndicator = document.getElementById('typing-indicator');
            const textToSpeech = document.getElementById('text-to-speech');
            const enableHistory = document.getElementById('enable-history');
            const themeSelector = document.getElementById('theme-selector');
            const clearChatButton = document.getElementById('clear-chat');
            
            // Load chat history if enabled
            if (localStorage.getItem('enableHistory') === 'true') {
                enableHistory.checked = true;
                const savedMessages = localStorage.getItem('chatHistory');
                if (savedMessages) {
                    chatMessages.innerHTML = savedMessages;
                    chatMessages.scrollTop = chatMessages.scrollHeight;
                }
            }
            
            // Theme selector
            themeSelector.addEventListener('change', function() {
                if (this.value === 'dark') {
                    document.body.classList.add('dark-mode');
                } else {
                    document.body.classList.remove('dark-mode');
                }
            });
            
            // Document upload preview
            documentUpload.addEventListener('change', function() {
                if (this.files.length > 0) {
                    uploadPreview.classList.remove('d-none');
                    uploadPreview.innerHTML = `<p class="text-success">Document ready: ${this.files[0].name}</p>`;
                } else {
                    uploadPreview.classList.add('d-none');
                }
            });
            
            // Clear chat
            clearChatButton.addEventListener('click', function() {
                chatMessages.innerHTML = `
                    <div class="message bot-message">
                        Hello! I'm your medical and legal assistant. You can ask me questions, upload documents for analysis, or both. How can I help you today?
                    </div>
                `;
                localStorage.removeItem('chatHistory');
            });
            
            // Add message function
            function addMessage(text, sender) {
                const messageDiv = document.createElement('div');
                messageDiv.classList.add('message', sender === 'user' ? 'user-message' : 'bot-message');
                messageDiv.innerText = text;
                
                chatMessages.appendChild(messageDiv);
                chatMessages.scrollTop = chatMessages.scrollHeight;
                
                // Save to local storage if enabled
                if (enableHistory.checked) {
                    localStorage.setItem('enableHistory', 'true');
                    localStorage.setItem('chatHistory', chatMessages.innerHTML);
                }
            }

            // Chat form submission
            chatForm.addEventListener('submit', function(e) {
                e.preventDefault();
                
                const userMessage = userInput.value.trim();
                if (!userMessage) return;
                
                // Add user message to chat
                addMessage(userMessage, 'user');
                userInput.value = '';
                
                // Show typing indicator
                typingIndicator.style.display = 'block';

                // Prepare form data
                const formData = new FormData();
                formData.append('query', userMessage);
                formData.append('type', queryType.value);

                // Add document if uploaded
                if (documentUpload.files.length > 0) {
                    formData.append('document', documentUpload.files[0]);
                }

                // Send request to server - with timeout and error handling
                const fetchTimeout = function(url, options, timeout = 30000) {
                    return Promise.race([
                        fetch(url, options),
                        new Promise((_, reject) => 
                            setTimeout(() => reject(new Error('Request timed out')), timeout)
                        )
                    ]);
                };

                fetchTimeout('/ask', {
                    method: 'POST',
                    body: formData
                }, 60000) // 60 second timeout for large files
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`Server responded with status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    // Hide typing indicator
                    typingIndicator.style.display = 'none';
                    
                    // Add bot response to chat
                    if (data.error) {
                        addMessage(`Error: ${data.error}`, 'bot');
                    } else {
                        addMessage(data.response, 'bot');
                        
                        // Text-to-speech if enabled
                        if (textToSpeech.checked && 'speechSynthesis' in window) {
                            const speech = new SpeechSynthesisUtterance(data.response);
                            window.speechSynthesis.speak(speech);
                        }
                    }
                    
                    // Clear file upload
                    documentUpload.value = '';
                    uploadPreview.classList.add('d-none');
                })
                .catch(error => {
                    typingIndicator.style.display = 'none';
                    addMessage(`Error: Could not connect to the server. ${error.message}`, 'bot');
                    console.error('Fetch error:', error);
                });
            });
        });
    </script>
</body>
</html>""")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    try:
        # Increase timeout for large files
        request.timeout = 60  # seconds
        
        query = request.form.get('query', '')
        query_type = request.form.get('type', 'general')
        
        document_text = None
        
        # Check if a file was uploaded
        if 'document' in request.files and request.files['document'].filename != '':
            file = request.files['document']
            
            # Validate file size (limit to 10MB)
            if file.content_length and file.content_length > 10 * 1024 * 1024:
                return jsonify({"error": "File too large. Please upload files smaller than 10MB."})
                
            file_bytes = file.read()
            
            if len(file_bytes) == 0:
                return jsonify({"error": "Empty file uploaded."})
            
            # Process based on file type
            if file.filename.lower().endswith('.pdf'):
                document_text = process_pdf_with_ocr(file_bytes)
            elif file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                document_text = extract_text_from_image(file_bytes)
            else:
                return jsonify({"error": "Unsupported file format. Please upload PDF or image files."})
        
        # Generate prompt based on query type and document if available
        prompt = get_prompt_for_query_type(query_type, document_text)
        
        # Prepare the final prompt with the user query
        final_prompt = f"{prompt}\n\nUser Query: {query}"
        
        # Handle potential API errors
        try:
            if document_text and len(document_text) > 100:
                # If document is provided and has content
                response_text = call_mistral_api(final_prompt)
            else:
                # For regular text queries or if document extraction failed
                response_text = call_mistral_api(query)
            
            return jsonify({"response": response_text})
        except Exception as api_error:
            # Handle specific API errors
            error_message = str(api_error)
            if "quota" in error_message.lower():
                return jsonify({"error": "API quota exceeded. Please try again later."})
            elif "unauthorized" in error_message.lower():
                return jsonify({"error": "API authentication failed. Please check your API key."})
            else:
                return jsonify({"error": f"API error: {error_message}"})
    
    except Exception as e:
        app.logger.error(f"Error processing request: {str(e)}")
        return jsonify({"error": f"An error occurred: {str(e)}"})

if __name__ == '__main__':
    # Create templates directory and HTML file on startup
    create_templates_directory()
    
    # Set larger request size limit (10MB)
    app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
    
    # Start the server
    app.run(debug=True, host='0.0.0.0', port=5000)