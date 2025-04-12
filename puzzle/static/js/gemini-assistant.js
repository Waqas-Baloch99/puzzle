const geminiResponses = [
    "Based on my analysis of your Python code, I suggest...",
    "Let me help you optimize that Python solution...",
    "Here's an efficient approach using Python's built-in features...",
    "I've analyzed multiple solutions, and here's the most Pythonic way...",
    "According to Python best practices, you might want to consider...",
    "Let me explain this Python concept in detail...",
    "I can help you debug that Python code. First, let's check...",
    "Here's how you can improve your Python code performance...",
    "That's an interesting Python challenge. Here's my approach...",
    "From my vast knowledge base, here's the optimal Python solution..."
];

function initGeminiAssistant() {
    const chatTrigger = document.getElementById('chatTrigger');
    const chatBox = document.getElementById('chatBox');
    const chatClose = document.getElementById('chatClose');
    const chatInput = document.getElementById('chatInput');
    const chatSend = document.getElementById('chatSend');
    const chatMessages = document.getElementById('chatMessages');

    // Check if required elements exist
    if (!chatTrigger || !chatBox || !chatClose || !chatInput || !chatSend || !chatMessages) {
        console.warn('Chat elements not found. Chat functionality disabled.');
        return;
    }

    chatTrigger.addEventListener('click', () => {
        chatBox.classList.toggle('active');
        const badge = chatTrigger.querySelector('.notification-badge');
        if (badge) badge.remove();
        chatTrigger.classList.add('shake-animation');
        setTimeout(() => chatTrigger.classList.remove('shake-animation'), 1000);
    });

    chatClose.addEventListener('click', () => {
        chatBox.classList.remove('active');
    });

    function addMessage(text, sender) {
        const messageElement = document.createElement('div');
        messageElement.className = `message ${sender}`;
        messageElement.textContent = text;
        
        if (sender === 'assistant') {
            messageElement.style.animation = 'fadeInUp 0.5s ease-out';
        }
        
        chatMessages.appendChild(messageElement);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function generateGeminiResponse() {
        return geminiResponses[Math.floor(Math.random() * geminiResponses.length)];
    }

    function handleUserInput() {
        const message = chatInput.value.trim();
        if (message === '') return;

        addMessage(message, 'user');
        chatInput.value = '';
        
        // Show typing animation
        const typingElement = document.createElement('div');
        typingElement.className = 'message assistant typing';
        typingElement.innerHTML = '<span class="typing-dots"><span>.</span><span>.</span><span>.</span></span>';
        chatMessages.appendChild(typingElement);
        
        // Simulate AI thinking time
        setTimeout(() => {
            typingElement.remove();
            addMessage(generateGeminiResponse(), 'assistant');
        }, 1500);
    }

    chatSend.addEventListener('click', handleUserInput);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleUserInput();
    });

    // Show notification after delay
    setTimeout(() => {
        if (!chatBox.classList.contains('active')) {
            const badge = document.createElement('span');
            badge.className = 'notification-badge';
            badge.textContent = '1';
            chatTrigger.appendChild(badge);
        }
    }, 5000);
}

// Ensure DOM is loaded before initializing
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initGeminiAssistant);
} else {
    initGeminiAssistant();
}
