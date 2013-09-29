class RenameMedicalDetailsTypeToKind < ActiveRecord::Migration
  def change
    rename_column :medical_details, :type, :kind
  end
end
