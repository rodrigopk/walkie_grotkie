import type { ReactNode } from "react";
import {
  FaRotate,
  FaGear,
  FaPersonWalking,
  FaHouse,
  FaRegCircleQuestion,
  FaMicrophoneLines,
} from "react-icons/fa6";

interface SmallButtonsProps {
  onRestart?: () => void;
  onHome?: () => void;
  onCycleAnimation?: () => void;
  onSettings?: () => void;
  onHelp?: () => void;
  onVoice?: () => void;
}

interface ButtonDef {
  className: string;
  onClick?: () => void;
  label: string;
  testId: string;
  icon: ReactNode;
}

/**
 * Two rows of small function buttons below the PTT button.
 *
 * Row 1 (left to right):
 *   ⌂ Home        — navigates back to the main screen
 *   ✦ Anim cycle  — cycles through Grot animations
 *   ⚙ Settings    — opens the settings view
 *
 * Row 2 (left to right):
 *   ↻ Restart     — tears down and restarts the BLE + OpenAI session
 *   ? Help        — shows the help screen
 *   ♪ Voice       — opens the voice picker screen
 */
export default function SmallButtons({
  onRestart,
  onHome,
  onCycleAnimation,
  onSettings,
  onHelp,
  onVoice,
}: SmallButtonsProps) {
  const buttons: ButtonDef[] = [
    {
      className: "small-btn-home",
      onClick: onHome,
      label: "Home",
      testId: "home-button",
      icon: <FaHouse />,
    },
    {
      className: "small-btn-anim",
      onClick: onCycleAnimation,
      label: "Cycle animation",
      testId: "cycle-animation-button",
      icon: <FaPersonWalking />,
    },
    {
      className: "small-btn-settings",
      onClick: onSettings,
      label: "Settings",
      testId: "settings-button",
      icon: <FaGear />,
    },
    {
      className: "small-btn-restart",
      onClick: onRestart,
      label: "Restart session",
      testId: "restart-button",
      icon: <FaRotate />,
    },
    {
      className: "small-btn-help",
      onClick: onHelp,
      label: "Help",
      testId: "help-button",
      icon: <FaRegCircleQuestion />,
    },
    {
      className: "small-btn-voice",
      onClick: onVoice,
      label: "Voice",
      testId: "voice-button",
      icon: <FaMicrophoneLines />,
    },
  ];

  return (
    <div className="device-small-buttons" data-testid="small-buttons">
      {buttons.map((btn) => (
        <button
          key={btn.testId}
          className={`small-btn ${btn.className}`}
          onClick={btn.onClick}
          aria-label={btn.label}
          data-testid={btn.testId}
        >
          {btn.icon}
        </button>
      ))}
    </div>
  );
}
