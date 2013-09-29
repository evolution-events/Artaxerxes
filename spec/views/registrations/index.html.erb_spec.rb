require 'spec_helper'

describe "registrations/index" do
  before(:each) do
    @event = stub_model(Event, to_s: "some_event")

    assign(:registrations, [
      stub_model(Registration,
        :user => nil,
        :event => @event,
        :status => "Status"
      ),
      stub_model(Registration,
        :user => nil,
        :event => @event,
        :status => "Status"
      )
    ])
  end

  it "renders a list of registrations" do
    render
    # Run the generator again with the --webrat flag if you want to use webrat matchers
    assert_select "tr>td", :text => nil.to_s, :count => 2
    assert_select "tr>td", :text => @event.to_s, :count => 2
    assert_select "tr>td", :text => "Status".to_s, :count => 2
  end
end
