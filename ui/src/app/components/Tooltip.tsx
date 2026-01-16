import { useState, useEffect, useRef } from 'react';

interface TooltipProps {
  content: string;
  children: React.ReactNode;
  autoHideDuration?: number;
}

export function Tooltip({ content, children, autoHideDuration = 3000 }: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [shouldShow, setShouldShow] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout>();
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    // Detect mobile/touch devices
    const checkMobile = () => {
      setIsMobile('ontouchstart' in window || navigator.maxTouchPoints > 0);
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  const handleMouseEnter = () => {
    if (isMobile) return; // Disable on mobile
    
    setShouldShow(true);
    setIsVisible(true);
    
    // Clear any existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    
    // Set auto-hide timeout
    timeoutRef.current = setTimeout(() => {
      if (!shouldShow) return; // Don't hide if mouse left and came back
      setIsVisible(false);
    }, autoHideDuration);
  };

  const handleMouseLeave = () => {
    if (isMobile) return;
    
    setShouldShow(false);
    setIsVisible(false);
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
  };

  const handleTooltipMouseEnter = () => {
    if (isMobile) return;
    
    setShouldShow(true);
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
  };

  const handleTooltipMouseLeave = () => {
    if (isMobile) return;
    
    setShouldShow(false);
    setIsVisible(false);
  };

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return (
    <div className="relative inline-flex items-center">
      <div
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      >
        {children}
      </div>
      {isVisible && !isMobile && (
        <div 
          className="hidden lg:block absolute right-full mr-3 z-50 animate-in fade-in slide-in-from-right-2 duration-200"
          onMouseEnter={handleTooltipMouseEnter}
          onMouseLeave={handleTooltipMouseLeave}
        >
          <div className="w-48 max-w-[12rem] bg-card/95 backdrop-blur-xl border border-border/50 rounded-lg shadow-2xl shadow-primary/10 relative">
            {/* Glossy highlight */}
            <div className="absolute inset-0 bg-gradient-to-b from-white/[0.03] to-transparent rounded-lg pointer-events-none" />
            {/* Arrow pointer */}
            <div className="absolute right-0 top-1/2 translate-x-1 -translate-y-1/2 w-2 h-2 bg-card/95 border-r border-b border-border/50 rotate-45" />
            {/* Content */}
            <div className="px-3 py-2 relative z-10">
              <p className="text-xs text-foreground/90 leading-relaxed break-words">{content}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}