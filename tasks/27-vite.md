Write a note taking application in TypeScript using Vite in demo01/ directory

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