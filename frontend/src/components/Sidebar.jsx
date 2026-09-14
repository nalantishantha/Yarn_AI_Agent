import React, { useEffect, useState } from 'react';

export default function Sidebar({ currentThreadId, onSelectThread, onNewChat }) {
  const [sessions, setSessions] = useState([]);

  const fetchSessions = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/chat/sessions');
      const data = await res.json();
      setSessions(data);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, [currentThreadId]); 

  return (
    <div className="sidebar">
      <button className="new-chat-btn" onClick={onNewChat}>
        + New Chat
      </button>
      <div className="sessions-list">
        {sessions.map(session => (
          <div 
            key={session.thread_id} 
            className={`session-item ${session.thread_id === currentThreadId ? 'active' : ''}`}
            onClick={() => onSelectThread(session.thread_id)}
          >
            {session.title}
          </div>
        ))}
      </div>
    </div>
  );
}
