class ApplicationController < ActionController::Base
  # Prevent CSRF attacks by raising an exception.
  # For APIs, you may want to use :null_session instead.
  protect_from_forgery with: :exception

  before_action :set_current_user

  def set_current_user
    if params['current_user']
      session[:user] = params['current_user']
    end
    @current_user = User.find_by(username: session[:user])
  end
end

