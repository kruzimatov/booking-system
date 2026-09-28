import { useEffect } from "react";

export function usePageTitle(title: string): void {
  useEffect(() => {
    document.title = `${title} · Tashkent Grooming Studio`;
  }, [title]);
}
