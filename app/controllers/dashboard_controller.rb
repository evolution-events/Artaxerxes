class DashboardController < ApplicationController
  before_action :set_future_events, only: [:show]

  def show
  end

  private
    def set_future_events
      @future_events = Event.where("start_date > ?", Time.now)
    end
end
