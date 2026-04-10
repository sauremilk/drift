// Enum with mixed casing in members
enum Status {
    ACTIVE = "active",
    INACTIVE = "inactive",
    pendingReview = "pending_review",  // inconsistent: camelCase among SCREAMING_SNAKE
    ARCHIVED = "archived",
}

enum Direction {
    Up = "up",
    Down = "down",
    LEFT = "LEFT",  // inconsistent: SCREAMING_SNAKE among PascalCase
    Right = "right",
}
