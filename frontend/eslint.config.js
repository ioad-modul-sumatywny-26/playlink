import globals from 'globals';
import prettier from 'eslint-config-prettier';
import svelte from 'eslint-plugin-svelte';
import svelteConfig from './svelte.config.js';
import ts from 'typescript-eslint';

export default ts.config(
	{
		ignores: ['.svelte-kit/', 'dist/', 'build/']
	},
	...ts.configs.recommended,
	...svelte.configs['flat/recommended'],
	{
		languageOptions: {
			globals: {
				...globals.browser,
				...globals.node
			},
			ecmaVersion: 2022,
			sourceType: 'module'
		}
	},
	{
		files: ['**/*.svelte', '**/*.svelte.ts', '**/*.svelte.js'],
		languageOptions: {
			parserOptions: {
				projectService: true,
				extraFileExtensions: ['.svelte'],
				parser: ts.parser,
				svelteConfig
			}
		}
	},
	prettier,
	{
		rules: {
			'svelte/no-at-html-tags': 'warn',
			'svelte/no-navigation-without-resolve': 'off'
		}
	}
);
