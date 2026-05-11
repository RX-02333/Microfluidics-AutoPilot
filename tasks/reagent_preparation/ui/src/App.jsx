import React from 'react';
import AgentApp from '../../../../system/components/base/agent/ui/src/App.jsx';
import './index.css';

const App = () => {
    return (
        <div className="container">
            <div className="chat-fullscreen">
                <AgentApp />
            </div>
        </div>
    );
};

export default App;
