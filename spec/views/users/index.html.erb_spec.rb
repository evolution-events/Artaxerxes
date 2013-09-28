require 'spec_helper'

describe "users/index" do
  before(:each) do
    assign(:users, [
      stub_model(User,
        :first_name => "First Name",
        :preposition => "Preposition",
        :last_name => "Last Name",
        :username => "Username",
        :phone_number => "Phone Number",
        :email => "Email",
        :gender => "Gender",
        :hide_last_name => false
      ),
      stub_model(User,
        :first_name => "First Name",
        :preposition => "Preposition",
        :last_name => "Last Name",
        :username => "Username",
        :phone_number => "Phone Number",
        :email => "Email",
        :gender => "Gender",
        :hide_last_name => false
      )
    ])
  end

  it "renders a list of users" do
    render
    # Run the generator again with the --webrat flag if you want to use webrat matchers
    assert_select "tr>td", :text => "First Name".to_s, :count => 2
    assert_select "tr>td", :text => "Preposition".to_s, :count => 2
    assert_select "tr>td", :text => "Last Name".to_s, :count => 2
    assert_select "tr>td", :text => "Username".to_s, :count => 2
    assert_select "tr>td", :text => "Phone Number".to_s, :count => 2
    assert_select "tr>td", :text => "Email".to_s, :count => 2
    assert_select "tr>td", :text => "Gender".to_s, :count => 2
    assert_select "tr>td", :text => false.to_s, :count => 2
  end
end
