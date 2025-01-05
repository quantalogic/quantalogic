# Note Taking Application Specification

## Overview
Develop a note-taking application using TypeScript and Vite, located in the `demo01/` directory. The application will allow users to create, edit, delete, and organize notes.

## Features
1. **User Authentication**: Implement user accounts for personal note storage.
2. **Create Notes**: Users can create new notes with a title and content.
3. **Edit Notes**: Users can edit existing notes.
4. **Delete Notes**: Users can delete notes they no longer need.
5. **Organize Notes**: Users can categorize notes with tags or folders.
6. **Search Functionality**: Users can search for notes by title or content.
7. **Responsive Design**: Ensure the application works on both desktop and mobile devices.

## Tech Stack
- **Frontend**: TypeScript, React (or any other chosen framework)
- **Backend**: Node.js (if applicable)
- **Database**: (Optional) A lightweight database like SQLite or an in-memory solution for demo purposes.
- **Build Tool**: Vite for fast development and build processes.

## Development Guidelines
- Follow TypeScript best practices.
- Ensure code is modular and maintainable.
- Write unit tests for critical components.

# TypeScript Code Rules & Standards

## 1. Write Simple, Clear Code
- Readable > clever
- Minimal viable solution first
- Delete unused code
- No premature optimization

## 2. Function Rules
- Single responsibility
- ≤30 lines
- ≤6 parameters
- Descriptive names
- Type hints

## 3. Project Structure
```typescript
/project
  /src
    /feature1
      models.ts
      services.ts
      types.ts
      __tests__/
    /feature2
      ...
    main.ts
  /dist
  package.json
  tsconfig.json
  jest.config.ts
```

## 4. Development Practice
- Use standard libs/tools
- Choose well-maintained libs
- Handle errors explicitly 
- Regular refactoring
- Document WHY not WHAT
- Executable scripts
- Write tests first
- Test Must be written to be insensitive to changes of formatting and not based on strict rules of display

## 5. Code Reviews
- Question complexity
- Check for dupes
- Verify error handling
- Ensure consistency

## DEBUG PROCESS
1. Reproduce issue
2. Understand system
3. Form hypothesis
4. Test & verify
5. Document fix

## REMEMBER
• Simple = Maintainable
• Code for humans
• Complexity kills
• Requirements drive changes

## Additional TypeScript-Specific Guidelines

### Type Definitions
- Use explicit types over `any`
- Prefer interfaces for object types
- Use type unions/intersections when appropriate
- Leverage TypeScript's built-in utility types

### Configuration
```json
// tsconfig.json base configuration
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "CommonJS",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "outDir": "./dist",
    "rootDir": "./src"
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "**/*.test.ts"]
}
```

### Testing Setup
```typescript
// jest.config.ts
export default {
  preset: 'ts-jest',
  testEnvironment: 'node',
  testMatch: ['**/__tests__/**/*.ts', '**/?(*.)+(spec|test).ts'],
  coverageDirectory: 'coverage'
};