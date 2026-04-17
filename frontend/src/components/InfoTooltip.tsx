import { useState } from "react";
import { Link } from "react-router-dom";

interface Props {
  text: string;
  learnMoreAnchor?: string;
}

export default function InfoTooltip({ text, learnMoreAnchor }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <span className="relative inline-block align-middle ml-1">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        className="w-4 h-4 rounded-full bg-gray-200 text-gray-600 text-[10px] font-bold hover:bg-blue-100 hover:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-300"
        aria-label="More info"
      >
        ?
      </button>
      {open && (
        <span className="absolute z-20 left-1/2 -translate-x-1/2 mt-2 w-64 bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-sm text-gray-700 normal-case font-normal">
          <span className="block mb-1">{text}</span>
          {learnMoreAnchor && (
            <Link
              to={`/methodology#${learnMoreAnchor}`}
              className="text-blue-600 hover:underline text-xs"
            >
              Learn more →
            </Link>
          )}
        </span>
      )}
    </span>
  );
}
