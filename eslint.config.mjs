import tseslint from 'typescript-eslint';
export default [
  { ignores: ['**/node_modules/**', '.agents/**', '**/dist/**', '**/out-tsc/**', 'packages/contracts/src/**', 'internal/**', 'artifacts/**'] },
  ...tseslint.configs.recommended.map(config => ({ ...config, files: ['apps/desktop/src/**/*.ts'] })),
  { files: ['apps/desktop/src/**/*.ts'], rules: {
    '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', caughtErrors: 'none' }],
    'eqeqeq': 'error',
  } },
];
