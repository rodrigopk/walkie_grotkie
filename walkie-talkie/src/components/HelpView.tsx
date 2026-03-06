import {
  FaHouse,
  FaPersonWalking,
  FaGear,
  FaRotate,
  FaRegCircleQuestion,
  FaMicrophoneLines,
  FaPowerOff,
} from "react-icons/fa6";

const HELP_ENTRIES = [
  { icon: <FaPowerOff />, text: "Turn off the app" },
  { icon: <FaHouse />, text: "Home / chat screen" },
  { icon: <FaPersonWalking />, text: "Cycle Grot animations" },
  { icon: <FaGear />, text: "Settings (API key)" },
  { icon: <FaRotate />, text: "Restart session" },
  { icon: <FaRegCircleQuestion />, text: "This help screen" },
  { icon: <FaMicrophoneLines />, text: "Change Grot's voice" },
] as const;

/**
 * Help screen displayed inside the visor.
 * Shows each function button's icon alongside a short description.
 */
export default function HelpView() {
  return (
    <div className="device-screen" data-testid="help-view">
      <div className="screen-header" data-testid="screen-title">Help</div>
      <div className="help-view">
        {HELP_ENTRIES.map((entry, i) => (
          <div key={i} className="help-row" data-testid="help-row">
            <span className="help-icon">{entry.icon}</span>
            <span>{entry.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
