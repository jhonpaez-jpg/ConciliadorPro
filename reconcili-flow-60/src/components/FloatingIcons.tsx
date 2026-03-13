import { PieChart, FileText, Calculator, TrendingUp, Coins, Bot } from "lucide-react";

const icons = [
  { Icon: PieChart, className: "top-[10%] left-[5%]", delay: "0s", size: "w-10 h-10" },
  { Icon: FileText, className: "top-[20%] right-[10%]", delay: "2s", size: "w-14 h-14" },
  { Icon: Calculator, className: "bottom-[15%] left-[15%]", delay: "4s", size: "w-12 h-12" },
  { Icon: TrendingUp, className: "bottom-[25%] right-[20%]", delay: "1s", size: "w-10 h-10" },
  { Icon: Coins, className: "top-[40%] left-[20%]", delay: "3s", size: "w-11 h-11" },
  { Icon: Bot, className: "bottom-[40%] right-[5%]", delay: "5s", size: "w-10 h-10" },
];

export default function FloatingIcons() {
  return (
    <>
      {icons.map(({ Icon, className, delay, size }, i) => (
        <Icon
          key={i}
          className={`fixed ${className} ${size} text-primary-foreground/10 animate-float pointer-events-none z-0`}
          style={{ animationDelay: delay }}
        />
      ))}
    </>
  );
}
