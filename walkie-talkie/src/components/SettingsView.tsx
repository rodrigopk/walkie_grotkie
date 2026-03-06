import { useState } from "react";

interface SettingsViewProps {
  onSave: (key: string) => void;
  onCancel: () => void;
  initialKey?: string;
}

/**
 * Settings view rendered inside the visor.
 * Lets the user enter and save their OpenAI API key.
 */
export default function SettingsView({
  onSave,
  onCancel,
  initialKey = "",
}: SettingsViewProps) {
  const [key, setKey] = useState(initialKey);

  function handleSave() {
    const trimmed = key.trim();
    if (trimmed) onSave(trimmed);
  }

  return (
    <div className="device-screen" data-testid="settings-view">
      <div className="settings-view">
        <div className="settings-field">
          <label className="settings-label" htmlFor="api-key-input">
            OpenAI API Key
          </label>
          <input
            id="api-key-input"
            className="settings-input"
            type="password"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSave()}
            placeholder="sk-..."
            data-testid="api-key-input"
            autoComplete="off"
            spellCheck={false}
          />
        </div>
        <div className="settings-actions">
          <button
            className="settings-save-btn"
            onClick={handleSave}
            disabled={!key.trim()}
            data-testid="save-api-key-button"
          >
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
