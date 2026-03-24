import { save } from "../infra/storage";

export function render(): string {
  return save();
}
