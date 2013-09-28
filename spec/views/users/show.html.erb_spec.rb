require 'spec_helper'

describe "users/show" do
  before(:each) do
    @user = assign(:user, stub_model(User,
      :first_name => "First Name",
      :preposition => "Preposition",
      :last_name => "Last Name",
      :username => "Username",
      :phone_number => "Phone Number",
      :email => "Email",
      :gender => "Gender",
      :hide_last_name => false
    ))
  end

  it "renders attributes in <p>" do
    render
    # Run the generator again with the --webrat flag if you want to use webrat matchers
    rendered.should match(/First Name/)
    rendered.should match(/Preposition/)
    rendered.should match(/Last Name/)
    rendered.should match(/Username/)
    rendered.should match(/Phone Number/)
    rendered.should match(/Email/)
    rendered.should match(/Gender/)
    rendered.should match(/false/)
  end
end
