import React, { useState } from 'react'
import ChatInterface from './components/ChatInterface'
import Sidebar from './components/Sidebar'
import './index.css'

function App() {
  const [threadId, setThreadId] = useState(() => crypto.randomUUID());

  return (
    <div className="app-container">
      <Sidebar 
        currentThreadId={threadId} 
        onSelectThread={setThreadId} 
        onNewChat={() => setThreadId(crypto.randomUUID())} 
      />
      <div className="main-content">
        <ChatInterface threadId={threadId} />
      </div>
    </div>
  )
}

export default App
