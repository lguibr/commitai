package cli

import (
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"strconv"

	"github.com/urfave/cli/v2"

	"github.com/lguibr/comai/api"
	"github.com/lguibr/comai/env"
	"github.com/lguibr/comai/git"
	"github.com/lguibr/comai/helper"
)

func GetApp() *cli.App {

	return &cli.App{

		Name:  "git-commit-helper",
		Usage: "Generate git commit messages using GPT-4",

		Commands: []*cli.Command{

			{
				Name:      "back",
				Usage:     "Perform a git reset based on the number of steps back",
				UsageText: "comai back [number of steps]",

				Action: func(c *cli.Context) error {
					stepsBackStr := c.Args().Get(0)
					if stepsBackStr == "" {
						fmt.Println("Error: Please provide the number of steps back as an argument")
						os.Exit(1)
					}

					stepsBack, err := strconv.Atoi(stepsBackStr)
					if err != nil {
						fmt.Printf("Error: Invalid number of steps back: %v\n", err)
						os.Exit(1)
					}

					if err := git.PerformGitReset(stepsBack); err != nil {
						fmt.Printf("Error: Failed to perform git reset: %v\n", err)
						os.Exit(1)
					}

					fmt.Printf("Successfully performed git reset HEAD~%d.\n", stepsBack)
					return nil
				},
			},
			{
				Name:      "create-template",
				Usage:     "Create a commit message template for the repository",
				UsageText: "comai create-template [template content]",

				Action: func(c *cli.Context) error {
					template := c.Args().Get(0)
					if template == "" {
						fmt.Println("Error: Please provide the template content as an argument")
						os.Exit(1)
					}

					if err := git.SaveCommitTemplate(template); err != nil {
						fmt.Printf("Error: Failed to save template: %v\n", err)
						os.Exit(1)
					}

					fmt.Println("Template saved successfully.")
					return nil
				},
			},
		},
		Flags: []cli.Flag{

			&cli.StringFlag{
				Name:    "explanation",
				Aliases: []string{"e"},
				Usage:   "Add a high level explanation of the commit",
			},
			&cli.BoolFlag{
				Name:    "commit",
				Aliases: []string{"c"},
				Usage:   "Commit the changes with the generated message",
			},
			&cli.StringFlag{
				Name:    "template",
				Aliases: []string{"t"},
				Value:   env.TEMPLATE_COMMIT,
				Usage:   "Specify a commit message template",
			},
			&cli.BoolFlag{
				Name:    "add",
				Aliases: []string{"a"},
				Usage:   "Stage all changes before generating the commit message",
			},
			&cli.StringFlag{
				Name:    "model",
				Aliases: []string{"m"},
				Value:   "gpt-4",
				Usage:   "Set the engine model to be used",
			},
		},
		Action: func(c *cli.Context) error {
			if env.OpenAI_API_KEY == "" {
				fmt.Println("Error: OPENAI_API_KEY environment variable not set")
				os.Exit(1)
			}

			if c.Bool("add") {
				err := git.StageAllChanges()
				if err != nil {
					fmt.Println("Error: Failed to stage all changes")
					os.Exit(1)
				}
			}

			diff, err := git.GetStagedChangesDiff()
			if err != nil {
				fmt.Println("Error: Failed to get staged diff")
				os.Exit(1)
			}

			if diff == "" {
				fmt.Println("Warning: No staged changes found. Exiting.")
				os.Exit(0)
			}

			repoName, err := git.GetRepositoryName()
			if err != nil {
				fmt.Println("Error: Failed to get repository name")
				os.Exit(1)
			}

			branchName, err := git.GetCurrentBranchName()
			if err != nil {
				fmt.Println("Error: Failed to get current branch name")
				os.Exit(1)
			}

			formattedDiff := helper.FormatDiffWithRepoAndBranchInfo(repoName, branchName, diff)

			template, err := git.GetCommitTemplate()
			if err != nil {
				fmt.Println("Error: Failed to get commit template")
				os.Exit(1)
			}
			model := c.String("model")
			explanation := c.Args().Get(0)

			if explanation == "" {
				explanation = c.String("explanation")
			}

			payloadBytes, err := api.PrepareRequestPayload(formattedDiff, template, model, explanation)

			if err != nil {
				fmt.Println("Error: Failed to prepare request payload")
				os.Exit(1)
			}

			req, err := api.CreateAPIRequest(env.OpenAI_API_KEY, payloadBytes)
			if err != nil {
				fmt.Println("Error: Failed to create API request")
				os.Exit(1)
			}

			resp, err := api.SendAPIRequest(req)
			if err != nil {
				fmt.Println("Error: Failed to send API request")
				os.Exit(1)
			}
			defer resp.Body.Close()

			if resp.StatusCode != http.StatusOK {
				fmt.Println("Error: Failed to generate commit message using open_ai api")
				os.Exit(1)
			}

			responseBody, err := api.ReadResponseBody(resp)
			if err != nil {
				fmt.Println("Error: Failed to read response body")
				os.Exit(1)
			}

			commitMessage, apiError, err := api.ParseResponse(responseBody)
			if err != nil {
				fmt.Printf("Error: Failed to parse response: %v\n", err)
				os.Exit(1)
			}

			if apiError != "" {
				fmt.Printf("Error from OpenAI API: %s\n", apiError)
				os.Exit(1)
			}

			if c.Bool("commit") {
				err := git.CreateCommit(commitMessage)
				if err != nil {
					fmt.Println("Error: Failed to create commit")
					os.Exit(1)
				}
				fmt.Printf("Committed message: \n\n %s\n", commitMessage)
			} else {
				// Create a temporary file with the commit message
				tmpFile, err := os.CreateTemp("", "commit-*.txt")
				if err != nil {
					fmt.Println("Error: Failed to create temporary file")
					os.Exit(1)
				}
				defer os.Remove(tmpFile.Name())

				_, err = tmpFile.Write([]byte(commitMessage))
				if err != nil {
					fmt.Println("Error: Failed to write to temporary file")
					os.Exit(1)
				}
				tmpFile.Close()

				// Open git's default text editor with the temporary file
				cmd := exec.Command("git", "commit", "-e", "-F", tmpFile.Name())
				cmd.Stdin = os.Stdin
				cmd.Stdout = os.Stdout
				cmd.Stderr = os.Stderr
				err = cmd.Run()
				if err != nil {
					fmt.Println("Error: Failed to open git text editor")
					os.Exit(1)
				}
			}

			return nil
		},
	}
}
