'use client';

import React, { useState } from 'react';

export function AIChatAssistant() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<{ sender: 'user' | 'ai'; text: string }[]>([]);
  const [input, setInput] = useState('');

  const handleSend = () => {
    if (!input.trim()) return;
    setMessages((prev) => [...prev, { sender: 'user', text: input }]);
    // AI call logic
    setInput('');
  };

  return (
    <div className="fixed bottom-6 right-6 z-50">
      {!isOpen ? (
        <button
          onClick={() => setIsOpen(true)}
          className="bg-indigo-600 hover:bg-indigo-700 text-white rounded-full p-4 shadow-lg flex items-center gap-2 transition"
        >
          <span>✨ AI Sales Assistant</span>
        </button>
      ) : (
        <div className="w-80 h-96 bg-gray-900 border border-gray-800 rounded-xl shadow-2xl flex flex-col p-4">
          <div className="flex justify-between items-center pb-2 border-b border-gray-800">
            <h3 className="font-semibold text-white">AI Sales Assistant</h3>
            <button onClick={() => setIsOpen(false)} className="text-gray-400 hover:text-white">✕</button>
          </div>
          <div className="flex-1 overflow-y-auto my-2 space-y-2 text-sm text-gray-300">
            {messages.length === 0 && (
              <p className="text-gray-500 italic text-center mt-10">How can I assist your sales team today?</p>
            )}
            {messages.map((m, idx) => (
              <div key={idx} className={`p-2 rounded ${m.sender === 'user' ? 'bg-indigo-600 text-white self-end' : 'bg-gray-800 text-gray-200'}`}>
                {m.text}
              </div>
            ))}
          </div>
          <div className="flex gap-2 pt-2 border-t border-gray-800">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask AI..."
              className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-1 text-sm text-white focus:outline-none"
            />
            <button onClick={handleSend} className="bg-indigo-600 text-white px-3 py-1 rounded text-sm">Send</button>
          </div>
        </div>
      )}
    </div>
  );
}
