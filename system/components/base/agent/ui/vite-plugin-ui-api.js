
// vite-plugin-ui-api.js
// A Vite plugin to provide simple message queue API for python backend

export function uiMessageApiPlugin() {
    // Shared message queue variables (in-memory)
    const messageQueue = [];

    return {
        name: 'vite-plugin-ui-api',
        configureServer(server) {
            // Add middleware to handle API requests
            server.middlewares.use((req, res, next) => {

                // POST /ui/add_user_message
                if (req.method === 'POST' && req.url === '/ui/add_user_message') {
                    let body = '';
                    req.on('data', chunk => { body += chunk.toString(); });
                    req.on('end', () => {
                        try {
                            const data = JSON.parse(body);
                            if (data.message) {
                                messageQueue.push({ type: 'user', content: data.message });
                                res.statusCode = 200;
                                res.setHeader('Content-Type', 'application/json');
                                res.end(JSON.stringify({ status: 'success' }));
                            } else {
                                res.statusCode = 400;
                                res.end(JSON.stringify({ status: 'error', message: 'No message content' }));
                            }
                        } catch (e) {
                            res.statusCode = 400;
                            res.end(JSON.stringify({ status: 'error', message: 'Invalid JSON' }));
                        }
                    });
                    return;
                }

                // POST /ui/add_system_message
                if (req.method === 'POST' && req.url === '/ui/add_system_message') {
                    let body = '';
                    req.on('data', chunk => { body += chunk.toString(); });
                    req.on('end', () => {
                        try {
                            const data = JSON.parse(body);
                            if (data.message) {
                                messageQueue.push({ type: 'system', content: data.message });
                                res.statusCode = 200;
                                res.setHeader('Content-Type', 'application/json');
                                res.end(JSON.stringify({ status: 'success' }));
                            } else {
                                res.statusCode = 400;
                                res.end(JSON.stringify({ status: 'error', message: 'No message content' }));
                            }
                        } catch (e) {
                            res.statusCode = 400;
                            res.end(JSON.stringify({ status: 'error', message: 'Invalid JSON' }));
                        }
                    });
                    return;
                }

                // GET /ui/poll_messages
                if (req.method === 'GET' && req.url === '/ui/poll_messages') {
                    // Return all messages in queue and clear it
                    const messages = [...messageQueue];
                    messageQueue.length = 0; // Clear queue

                    res.statusCode = 200;
                    res.setHeader('Content-Type', 'application/json');
                    res.end(JSON.stringify({ messages: messages }));
                    return;
                }

                next();
            });
        }
    };
}
