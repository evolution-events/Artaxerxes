Logging in

Narrative:
As a visitor
I want to log in to the system
So that I have access to features that need authentication and/or authorization

Scenario 1: Filling in wrong username
Given that I fill in '..._l..' as my username
  and that username is incorrect
  and I fill in 'password' as my password
  and that password is correct
When I click 'log in'
Then I get an error saying that the username is not found
  and I see the same form again

Scenario 2: Filling in wrong password
Given that I fill in 'foobar' as my username
  and that username is correct
  and I fill in 'password' as my password
  and that password is incorrect
When I click 'log in'
Then I get an error saying that the password is incorrect for this user
  and I see the same form again

Scenario 3: Filling in right info
Given that I fill in 'foobar' as my username
  and that username is correct
  and I fill in 'password' as my password
  and that password is correct
When I click 'log in'
Then I get a message saying I have succesfully logged in
  and I get redirected to the dashboard page

