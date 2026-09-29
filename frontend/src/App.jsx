import React, { useState } from 'react'
import ChatInterface from './components/ChatInterface'
import Sidebar from './components/Sidebar'
import './index.css'

function App() {
  const [threadId, setThreadId] = useState(() => crypto.randomUUID());
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  return (
    <div className="app-container">
      <Sidebar 
        currentThreadId={threadId} 
        onSelectThread={setThreadId} 
        onNewChat={() => setThreadId(crypto.randomUUID())} 
        refreshTrigger={refreshTrigger}
      />
      <div className="main-content">
        <ChatInterface 
          threadId={threadId} 
          onChatUpdate={() => setRefreshTrigger(prev => prev + 1)}
        />
      </div>
    </div>
  )
}

export default App
