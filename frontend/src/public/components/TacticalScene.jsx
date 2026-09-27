import { useState } from "react";
import { Icon } from "../../components/ui/Icon";

const points = [
  [120, 210],
  [210, 130],
  [235, 275],
  [335, 195],
  [405, 105],
  [465, 255],
];

export function TacticalScene({ compact = false }) {
  const [paused, setPaused] = useState(false);
  return (
    <div
      className={`once-tactics ${compact ? "once-tactics-compact" : ""}`}
      data-paused={paused}
    >
      <div className="once-tactics-top">
        <span>
          <i /> VISIÓN DE JUEGO
        </span>
        <span>11 / 11</span>
      </div>
      <div className="once-tactics-stage" aria-hidden="true">
        <span className="once-orbit once-orbit-one" />
        <span className="once-orbit once-orbit-two" />
        <svg className="once-pitch-art" viewBox="0 0 600 390" fill="none">
          <defs>
            <linearGradient
              id={compact ? "pitchFillSmall" : "pitchFill"}
              x1="60"
              y1="40"
              x2="540"
              y2="360"
              gradientUnits="userSpaceOnUse"
            >
              <stop stopColor="#203554" />
              <stop offset="1" stopColor="#112039" />
            </linearGradient>
          </defs>
          <rect x="42" y="37" width="516" height="326" rx="5" fill="#081225" />
          <rect
            x="42"
            y="25"
            width="516"
            height="326"
            rx="5"
            fill={`url(#${compact ? "pitchFillSmall" : "pitchFill"})`}
            stroke="#6b83a7"
          />
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <rect
              key={i}
              x={60 + i * 80}
              y="44"
              width="40"
              height="288"
              fill="#ffffff"
              opacity=".025"
            />
          ))}
          <g stroke="#7387a5" strokeWidth="1.2">
            <path d="M60 44H540V332H60ZM300 44V332M60 110H132V266H60M540 110H468V266H540M60 154H89V222H60M540 154H511V222H540" />
            <circle cx="300" cy="188" r="48" />
            <circle cx="300" cy="188" r="3" fill="#7387a5" />
            <path d="M132 154Q174 188 132 222M468 154Q426 188 468 222" />
          </g>
          <path
            className="once-pass-path"
            d="M120 210 210 130 235 275 335 195 405 105 465 255"
            stroke="#c4f45b"
            strokeWidth="2"
            strokeDasharray="5 6"
          />
          {points.map(([x, y], i) => (
            <g
              key={x}
              className="once-player-dot"
              style={{ "--delay": `${i * 0.3}s` }}
            >
              <circle cx={x} cy={y} r="18" fill="#c4f45b" opacity=".09" />
              <circle
                cx={x}
                cy={y}
                r="9"
                fill="#c4f45b"
                stroke="#101d36"
                strokeWidth="3"
              />
              <text
                x={x}
                y={y + 29}
                textAnchor="middle"
                fill="#b4c1d6"
                fontSize="10"
                fontFamily="monospace"
              >
                {String(i + 6).padStart(2, "0")}
              </text>
            </g>
          ))}
          {[
            [166, 290],
            [335, 85],
            [420, 310],
            [500, 165],
          ].map(([x, y]) => (
            <circle
              key={x}
              cx={x}
              cy={y}
              r="7"
              fill="#152540"
              stroke="#6e85a8"
              strokeWidth="2"
            />
          ))}
        </svg>
        <div className="once-map-tag once-map-tag-a">
          <Icon name="shield" />
          <span>
            EQUIPOS<strong>Identidad que conecta.</strong>
          </span>
        </div>
        <div className="once-map-tag once-map-tag-b">
          <span className="once-tag-number">90′</span>
          <span>
            PARTIDOS<strong>Mucho más que un resultado.</strong>
          </span>
        </div>
        <span className="once-coordinate">4° 36′ N / 74° 04′ W</span>
      </div>
      <div className="once-tactics-bottom">
        <span>EL JUEGO SE ENTIENDE EN EQUIPO.</span>
        <button
          type="button"
          onClick={() => setPaused(!paused)}
          aria-label={paused ? "Reanudar animación" : "Pausar animación"}
          aria-pressed={paused}
        >
          <Icon name={paused ? "play" : "pause"} />
        </button>
      </div>
    </div>
  );
}
