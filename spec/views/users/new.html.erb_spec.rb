require 'spec_helper'

describe "users/new" do
  before(:each) do
    assign(:user, stub_model(User,
      :first_name => "MyString",
      :preposition => "MyString",
      :last_name => "MyString",
      :username => "MyString",
      :phone_number => "MyString",
      :email => "MyString",
      :gender => "MyString",
      :hide_last_name => false
    ).as_new_record)
  end

  it "renders new user form" do
    render

    # Run the generator again with the --webrat flag if you want to use webrat matchers
    assert_select "form[action=?][method=?]", users_path, "post" do
      assert_select "input#user_first_name[name=?]", "user[first_name]"
      assert_select "input#user_preposition[name=?]", "user[preposition]"
      assert_select "input#user_last_name[name=?]", "user[last_name]"
      assert_select "input#user_username[name=?]", "user[username]"
      assert_select "input#user_phone_number[name=?]", "user[phone_number]"
      assert_select "input#user_email[name=?]", "user[email]"
      assert_select "input#user_gender[name=?]", "user[gender]"
      assert_select "input#user_hide_last_name[name=?]", "user[hide_last_name]"
    end
  end
end
