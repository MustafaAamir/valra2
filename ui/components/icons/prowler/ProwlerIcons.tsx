import React from "react";

import { IconSvgProps } from "../../../types/index";

export const TrustreadyExtended: React.FC<IconSvgProps> = ({
  size,
  width = 216,
  height,
  ...props
}) => {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 1233.67 204.4"
      fill="none"
      class="text-prowler-black dark:text-prowler-white"
      height="204"
      width="216"
    >
      <text
        x="0"
        y="160"
        font-family="Futura, Futura Bold, sans-serif"
        font-weight="700"
        font-size="200"
        fill="currentColor"
        letter-spacing="0.02em"
      >Trustready</text>
    </svg>
  );
};

export const TrustreadyShort: React.FC<IconSvgProps> = ({
  size,
  width = 30,
  height,
  ...props
}) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 432.08 396.77"
    fill="none"
    class="text-prowler-black dark:text-prowler-white"
    height="204"
    width="30"
  >
    <text
      x="0"
      y="360"
      font-family="Futura, Futura Bold, sans-serif"
      font-weight="700"
      font-size="655"
      fill="currentColor"
      letter-spacing="0.00em"
    >T</text>
  </svg>
);
