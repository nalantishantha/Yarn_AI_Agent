import React, { useState } from 'react';

export default function StructuredFormInput({ onSubmitForm, isLoading }) {
  const [numYarns, setNumYarns] = useState(1);
  const [globalRequirements, setGlobalRequirements] = useState('');
  
  const initialYarnState = {
    material: '',
    color: '',
    maxPrice: '',
    maxLeadTime: '',
    priority: ''
  };

  const [yarns, setYarns] = useState([{ ...initialYarnState }]);

  const handleNumYarnsChange = (e) => {
    let num = parseInt(e.target.value);
    if (isNaN(num) || num < 1) num = 1;
    if (num > 10) num = 10;
    
    setNumYarns(num);
    
    setYarns(prev => {
      const newYarns = [...prev];
      if (num > prev.length) {
        for (let i = prev.length; i < num; i++) {
          newYarns.push({ ...initialYarnState });
        }
      } else if (num < prev.length) {
        newYarns.splice(num);
      }
      return newYarns;
    });
  };

  const handleYarnChange = (index, field, value) => {
    setYarns(prev => {
      const newYarns = [...prev];
      newYarns[index] = { ...newYarns[index], [field]: value };
      return newYarns;
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    
    let promptParts = [];
    promptParts.push(`I need an article with ${numYarns} yarn${numYarns > 1 ? 's' : ''}.`);
    
    yarns.forEach((yarn, index) => {
      let yarnParts = [];
      if (yarn.material) yarnParts.push(`${yarn.material}`);
      if (yarn.color) yarnParts.push(`color ${yarn.color}`);
      if (yarn.maxPrice) yarnParts.push(`under $${yarn.maxPrice}`);
      if (yarn.maxLeadTime) yarnParts.push(`max lead time ${yarn.maxLeadTime} days`);
      
      let yarnString = `Yarn ${index + 1}: ${yarnParts.join(', ')}`;
      if (yarn.priority) {
        yarnString += `. Prioritize: ${yarn.priority}`;
      }
      promptParts.push(yarnString);
    });
    
    if (globalRequirements.trim()) {
      promptParts.push(`Additional requirements: ${globalRequirements.trim()}`);
    }
    
    const finalPrompt = promptParts.join('\n');
    onSubmitForm(finalPrompt);
  };

  return (
    <form className="structured-form" onSubmit={handleSubmit}>
      <div className="form-header">
        <label>
          Number of Yarns:
          <input 
            type="number" 
            min="1" 
            max="10" 
            value={numYarns} 
            onChange={handleNumYarnsChange}
            className="num-yarns-input"
          />
        </label>
      </div>

      <div className="yarns-container">
        {yarns.map((yarn, index) => (
          <div key={index} className="yarn-section">
            <h4>Yarn {index + 1}</h4>
            <div className="yarn-grid">
              <div className="form-group">
                <label>Material / Fiber Type</label>
                <input 
                  type="text" 
                  value={yarn.material} 
                  onChange={(e) => handleYarnChange(index, 'material', e.target.value)}
                  placeholder="e.g. Cotton"
                />
              </div>
              <div className="form-group">
                <label>Color</label>
                <input 
                  type="text" 
                  value={yarn.color} 
                  onChange={(e) => handleYarnChange(index, 'color', e.target.value)}
                  placeholder="e.g. Red"
                />
              </div>

              <div className="form-group">
                <label>Max Price ($)</label>
                <input 
                  type="number"
                  step="0.01" 
                  value={yarn.maxPrice} 
                  onChange={(e) => handleYarnChange(index, 'maxPrice', e.target.value)}
                  placeholder="e.g. 15.50"
                />
              </div>
              <div className="form-group">
                <label>Max Lead Time (Days)</label>
                <input 
                  type="number" 
                  value={yarn.maxLeadTime} 
                  onChange={(e) => handleYarnChange(index, 'maxLeadTime', e.target.value)}
                  placeholder="e.g. 30"
                />
              </div>
              <div className="form-group full-width">
                <label>Priorities & Preferences</label>
                <input 
                  type="text" 
                  value={yarn.priority} 
                  onChange={(e) => handleYarnChange(index, 'priority', e.target.value)}
                  placeholder="e.g. 100% price"
                />
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="form-group global-req">
        <label>Global Requirements</label>
        <textarea 
          value={globalRequirements} 
          onChange={(e) => setGlobalRequirements(e.target.value)}
          placeholder="e.g. Exclude supplier Toray"
          rows="2"
        />
      </div>

      <button type="submit" className="submit-form-btn" disabled={isLoading}>
        {isLoading ? 'Sending...' : 'Send Requirements'}
      </button>
    </form>
  );
}
