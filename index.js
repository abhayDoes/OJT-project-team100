lucide.createIcons(); //create icons for the website

const API_BASE_URL = 'http://localhost:5002'; //base url for the api

async function callApi(endpoint, method, body) {
    const maxRetries = 3;
    for (let attempt = 0; attempt < maxRetries; attempt++) {
        try {
            const response = await fetch(`${API_BASE_URL}${endpoint}`, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                },
                // Ensure body is stringified correctly
                body: body ? JSON.stringify(body) : undefined, 
            });

            const result = await response.json();

            if (!response.ok) {
                // If it's a 4xx or 5xx error that is not a temporary failure, stop retrying
                displayMessage(`API Error [${response.status}]: ${result.error || response.statusText}`, 'error');
                throw new Error(`[${response.status}] ${result.error || response.statusText}`);
            }
            
            return result;

        } catch (error) {
            if (attempt < maxRetries - 1) {
                // Exponential backoff: Wait 1s, 2s, 4s...
                await new Promise(resolve => setTimeout(resolve, Math.pow(2, attempt) * 1000));
            } else {
                // Final error handling
                console.error("API Call Failed:", error);
                if (!error.message.includes('API Error')) {
                     displayMessage(`Connection Error: Ensure the Python server is running on ${API_BASE_URL}.`, 'error');
                }
                return null;
            }
        }
    }
}
