import { MenuIcon } from "lucide-react";
import Link from "next/link";

import { TrustreadyShort } from "@/components/icons";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Menu } from "@/components/ui/sidebar/menu";

import { Button } from "../button/button";

export function SheetMenu() {
  return (
    <Sheet>
      <SheetTrigger className="lg:hidden" asChild>
        <Button className="h-8" variant="outline" size="icon">
          <MenuIcon size={20} />
        </Button>
      </SheetTrigger>
      <SheetContent
        className="flex h-full flex-col px-3 dark:bg-prowler-theme-midnight sm:w-72"
        side="left"
      >
        <SheetHeader>
          <SheetTitle className="sr-only">Sidebar</SheetTitle>
          <SheetDescription className="sr-only" />
          <Button
            className="flex items-center justify-center pb-2 pt-1"
            variant="link"
            asChild
          >
            <Link href="/" className="flex items-center gap-2">
              <TrustreadyShort />
            </Link>
          </Button>
        </SheetHeader>
        <Menu isOpen />
      </SheetContent>
    </Sheet>
  );
}
